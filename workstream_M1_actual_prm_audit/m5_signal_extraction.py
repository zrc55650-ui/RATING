#!/usr/bin/env python3
"""M5 signals B2/B3: step entropy and masked answer-probability drop.

Runs on a GPU box with Qwen3-8B (transformers >= 4.51). For each of the 600
target steps computes:

  B2  target-step mean token NLL and mean predictive entropy, teacher-forced
      over "Problem + Steps 1..k" (the step's own tokens given its prefix);
  B3  I_mask = log p(answer | steps 0..k) - log p(answer | steps 0..k-1),
      i.e. the drop in gold-answer log-probability when the target step is
      deleted under the same truncation semantics as the intervention study.

Usage:
    python m5_signal_extraction.py --model Qwen/Qwen3-8B \
        --input prm_scoring_input.jsonl --output m5_signals.jsonl
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def build_text(problem: str, steps: list[str], last: int) -> str:
    parts = [f"Problem: {problem}", "", "Solution:"]
    for index in range(last + 1):
        parts.append(f"Step {index + 1}:\n{steps[index]}")
    return "\n\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen3-8B")
    parser.add_argument("--input", default="prm_scoring_input.jsonl")
    parser.add_argument("--output", default="m5_signals.jsonl")
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map="cuda"
    ).eval()

    out_path = Path(args.output)
    done = set()
    if out_path.exists():
        with out_path.open(encoding="utf-8") as handle:
            done = {json.loads(line)["step_id"] for line in handle if line.strip()}

    def token_logprobs(text: str, continuation: str) -> tuple[float, list[float]]:
        """Sum logprob of continuation tokens given text; also per-token list."""
        prefix_ids = tokenizer(text, return_tensors="pt").input_ids
        full_ids = tokenizer(text + continuation, return_tensors="pt").input_ids
        n_prefix = prefix_ids.shape[1]
        full_ids = full_ids.to(model.device)
        with torch.no_grad():
            logits = model(full_ids).logits.float()
        logprobs = torch.log_softmax(logits[0, :-1], dim=-1)
        targets = full_ids[0, 1:]
        per_token = logprobs[range(len(targets)), targets]
        span = per_token[n_prefix - 1 :]
        return float(span.sum().item()), [float(x) for x in span]

    def step_stats(problem: str, steps: list[str], k: int) -> dict:
        prefix_text = build_text(problem, steps, k - 1) if k > 0 else (
            f"Problem: {problem}\n\nSolution:"
        )
        step_text = f"\n\nStep {k + 1}:\n{steps[k]}"
        prefix_ids = tokenizer(prefix_text, return_tensors="pt").input_ids
        full_ids = tokenizer(prefix_text + step_text, return_tensors="pt").input_ids.to(
            model.device
        )
        n_prefix = prefix_ids.shape[1]
        with torch.no_grad():
            logits = model(full_ids).logits.float()
        logprobs = torch.log_softmax(logits[0, :-1], dim=-1)
        targets = full_ids[0, 1:]
        per_token = logprobs[range(len(targets)), targets][n_prefix - 1 :]
        probs = torch.exp(logprobs[n_prefix - 1 :])
        entropy = -(probs * logprobs[n_prefix - 1 :]).sum(dim=-1)
        return {
            "target_mean_nll": float(-per_token.mean().item()),
            "target_sum_nll": float(-per_token.sum().item()),
            "target_tokens": int(per_token.shape[0]),
            "target_mean_entropy": float(entropy.mean().item()),
        }

    with Path(args.input).open(encoding="utf-8") as handle, out_path.open(
        "a", encoding="utf-8"
    ) as sink:
        for line_number, line in enumerate(handle):
            record = json.loads(line)
            if record["step_id"] in done:
                continue
            steps = record["steps"]
            k = record["target_index"]
            answer_text = f"\n\nTherefore, the final answer is: {record['ground_truth_answer']}"
            try:
                stats = step_stats(record["problem"], steps, k)
                with_target, _ = token_logprobs(
                    build_text(record["problem"], steps, k), answer_text
                )
                without_target, _ = token_logprobs(
                    build_text(record["problem"], steps, k - 1)
                    if k > 0
                    else f"Problem: {record['problem']}\n\nSolution:",
                    answer_text,
                )
                result = {
                    "step_id": record["step_id"],
                    **stats,
                    "answer_logp_with_target": with_target,
                    "answer_logp_without_target": without_target,
                    "mask_importance": with_target - without_target,
                    "status": "ok",
                }
            except Exception as error:  # noqa: BLE001
                result = {"step_id": record["step_id"], "status": f"error: {str(error)[:150]}"}
            sink.write(json.dumps(result, ensure_ascii=False) + "\n")
            sink.flush()
            if (line_number + 1) % 50 == 0:
                print(f"{line_number + 1} processed")
    print("done ->", out_path)


if __name__ == "__main__":
    main()
