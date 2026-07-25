#!/usr/bin/env python3
"""M1 adapter: score all 600 trajectories with Math-Shepherd's trained PRM.

Checkpoint: peiyi9979/math-shepherd-mistral-7b-prm. Per the model card, steps
are joined as "Step i: ... ки" lines appended to the question; the PRM reads
P(good) from the '+'/'-' logits at each 'ки' tag position.

Usage (GPU box):
    python score_with_math_shepherd.py --input prm_scoring_input.jsonl

Output schema matches score_with_qwen_prm.py (step_id, model, status,
step_scores, target_index, target_score).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="peiyi9979/math-shepherd-mistral-7b-prm")
    parser.add_argument("--input", default="prm_scoring_input.jsonl")
    parser.add_argument("--output", default="prm_scores_math_shepherd_mistral_7b.jsonl")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map=args.device
    ).eval()
    good, bad, step_tag = "+", "-", "ки"
    candidate_tokens = tokenizer.encode(f"{good} {bad}")[1:]
    step_tag_id = tokenizer.encode(f"{step_tag}")[-1]

    output_path = Path(args.output)
    done = set()
    if output_path.exists():
        with output_path.open(encoding="utf-8") as handle:
            done = {json.loads(line)["step_id"] for line in handle}
        print(f"resuming: {len(done)} already scored")

    with Path(args.input).open(encoding="utf-8") as handle, output_path.open(
        "a", encoding="utf-8"
    ) as sink:
        for line in handle:
            record = json.loads(line)
            if record["step_id"] in done:
                continue
            joined = "\n".join(
                f"Step {i + 1}: {text} {step_tag}"
                for i, text in enumerate(record["steps"])
            )
            text = f"{record['problem']} {joined}"
            input_ids = torch.tensor(
                [tokenizer.encode(text)[-4096:]], device=model.device
            )
            with torch.no_grad():
                logits = model(input_ids).logits[:, :, candidate_tokens]
                scores = logits.softmax(dim=-1)[:, :, 0]
                step_scores = scores[input_ids == step_tag_id].float().tolist()
            status = "ok" if len(step_scores) == len(record["steps"]) else "step_count_mismatch"
            target_index = record["target_index"]
            sink.write(
                json.dumps(
                    {
                        "step_id": record["step_id"],
                        "model": args.model,
                        "status": status,
                        "step_scores": step_scores,
                        "target_index": target_index,
                        "target_score": (
                            step_scores[target_index]
                            if target_index < len(step_scores)
                            else None
                        ),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            sink.flush()
    print("done ->", output_path)


if __name__ == "__main__":
    main()
