import argparse
import csv
import json
import random
from pathlib import Path

from transformers import AutoTokenizer


def read_embedded_payload(path: Path) -> dict:
    html = path.read_text(encoding="utf-8")
    prefix = "const DATA = "
    suffix = ";\n    const samples = DATA.samples;"
    start = html.find(prefix)
    if start < 0:
        raise ValueError(f"Embedded DATA not found in {path}")
    start += len(prefix)
    end = html.find(suffix, start)
    if end < 0:
        raise ValueError(f"Embedded DATA end not found in {path}")
    return json.loads(html[start:end])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-html", default="prm800k_ai_600_human_calibrated_flash.html")
    parser.add_argument("--pairs-csv", default="qwen3-8b_deletion_pairs.csv")
    parser.add_argument("--output-jsonl", default="qwen3-8b_placebo_selection.jsonl")
    parser.add_argument("--output-summary", default="qwen3-8b_placebo_selection_summary.json")
    parser.add_argument("--model", default="Qwen/Qwen3-8B")
    parser.add_argument("--seed", type=int, default=20260723)
    parser.add_argument("--max-placebos", type=int, default=4)
    parser.add_argument("--lower-ratio", type=float, default=0.8)
    parser.add_argument("--upper-ratio", type=float, default=1.2)
    args = parser.parse_args()

    payload = read_embedded_payload(Path(args.input_html))
    samples = sorted(payload["samples"], key=lambda row: int(row["displayOrder"]))
    if len(samples) != 600:
        raise ValueError(f"Expected 600 samples, found {len(samples)}")

    pair_metadata: dict[str, dict] = {}
    pair_counts: dict[str, int] = {}
    with Path(args.pairs_csv).open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            sample_id = row["sampleId"]
            pair_counts[sample_id] = pair_counts.get(sample_id, 0) + 1
            pair_metadata.setdefault(
                sample_id,
                {
                    "rating": int(row["rating"]),
                    "position": row["position"],
                    "stepTypeLabel": row["stepTypeLabel"],
                    "removableLabel": row["removableLabel"],
                },
            )
    if len(pair_metadata) != 600 or any(count != 4 for count in pair_counts.values()):
        raise ValueError("Pairs CSV must contain exactly four runs for each of 600 samples")

    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=True)
    rng = random.Random(args.seed)
    selected_rows: list[dict] = []
    skipped: list[dict] = []
    candidate_count_distribution: dict[str, int] = {}

    for sample in samples:
        sample_id = str(sample["id"])
        metadata = pair_metadata.get(sample_id)
        if metadata is None:
            raise ValueError(f"Sample {sample_id} is missing from pairs CSV")
        steps = list(sample["steps"])
        target_index = int(sample["stepIndex"])
        if not 0 <= target_index < len(steps):
            raise ValueError(f"Invalid target index for {sample_id}")

        token_lengths = [
            len(tokenizer.encode(str(step), add_special_tokens=False)) for step in steps
        ]
        target_length = token_lengths[target_index]
        lower = args.lower_ratio * target_length
        upper = args.upper_ratio * target_length
        candidates = [
            index
            for index, length in enumerate(token_lengths)
            if index != target_index and lower <= length <= upper
        ]
        candidate_count_distribution[str(len(candidates))] = (
            candidate_count_distribution.get(str(len(candidates)), 0) + 1
        )
        if not candidates:
            skipped.append(
                {
                    "sampleId": sample_id,
                    "displayOrder": int(sample["displayOrder"]),
                    "targetStepIndex": target_index,
                    "targetStepTokens": target_length,
                    "trajectorySteps": len(steps),
                }
            )
            continue

        chosen = rng.sample(candidates, min(args.max_placebos, len(candidates)))
        for placebo_order, placebo_index in enumerate(chosen, start=1):
            placebo_length = token_lengths[placebo_index]
            selected_rows.append(
                {
                    "taskId": f"{sample_id}|placebo{placebo_order}|step{placebo_index}",
                    "sampleId": sample_id,
                    "displayOrder": int(sample["displayOrder"]),
                    "placeboOrder": placebo_order,
                    "placeboStepIndex": placebo_index,
                    "placeboStepNumber": placebo_index + 1,
                    "placeboStepTokens": placebo_length,
                    "targetStepIndex": target_index,
                    "targetStepNumber": target_index + 1,
                    "targetStepTokens": target_length,
                    "lengthRatio": round(placebo_length / target_length, 6),
                    "eligibleCandidateCount": len(candidates),
                    "trajectorySteps": len(steps),
                    "rating": metadata["rating"],
                    "position": metadata["position"],
                    "stepTypeLabel": metadata["stepTypeLabel"],
                    "removableLabel": metadata["removableLabel"],
                    "groundTruthAnswer": str(sample["groundTruthAnswer"]),
                }
            )

    output_path = Path(args.output_jsonl)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in selected_rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")

    selected_per_sample: dict[str, int] = {}
    for row in selected_rows:
        selected_per_sample[row["sampleId"]] = selected_per_sample.get(row["sampleId"], 0) + 1
    summary = {
        "modelTokenizer": args.model,
        "seed": args.seed,
        "lengthWindow": [args.lower_ratio, args.upper_ratio],
        "maxPlacebosPerTarget": args.max_placebos,
        "totalSamples": len(samples),
        "eligibleSamples": len(selected_per_sample),
        "skippedSamples": len(skipped),
        "selectedPlaceboRuns": len(selected_rows),
        "selectedCountDistribution": {
            str(count): sum(1 for value in selected_per_sample.values() if value == count)
            for count in range(1, args.max_placebos + 1)
        },
        "eligibleCandidateCountDistribution": dict(
            sorted(candidate_count_distribution.items(), key=lambda item: int(item[0]))
        ),
        "skipped": skipped,
    }
    Path(args.output_summary).write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "skipped"}))


if __name__ == "__main__":
    main()
