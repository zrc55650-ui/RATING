#!/usr/bin/env python3
"""M1 adapter: score all 600 trajectories with a discriminative Qwen-style PRM.

Target checkpoint: Qwen/Qwen2.5-Math-PRM-7B (or PRM800K-trained variants with
the same interface). Requires a GPU box with `transformers` + `torch`
(bf16, ~15 GB VRAM). Not runnable on the 16 GB M1 Pro laptop.

Input format (per Qwen2.5-Math-PRM model card): a chat conversation whose
assistant turn joins reasoning steps with the special "<extra_0>" separator;
the PRM head yields P(step correct) at each separator position.

Usage:
    python score_with_qwen_prm.py --model Qwen/Qwen2.5-Math-PRM-7B \
        --input prm_scoring_input.jsonl --output prm_scores_qwen25_math_prm_7b.jsonl

Output: one JSON line per step_id with per-step probabilities for the full
trajectory plus the target-step score; feed into analyze_prm_scores.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

SYSTEM_PROMPT = (
    "Please reason step by step, and put your final answer within \\boxed{}."
)


def build_conversation(record: dict) -> list[dict]:
    joined = "<extra_0>".join(record["steps"]) + "<extra_0>"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": record["problem"]},
        {"role": "assistant", "content": joined},
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="Qwen/Qwen2.5-Math-PRM-7B")
    parser.add_argument("--input", default="prm_scoring_input.jsonl")
    parser.add_argument("--output", default=None)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--dtype", default="bfloat16")
    args = parser.parse_args()

    import torch
    from transformers import AutoModel, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        args.model,
        torch_dtype=getattr(torch, args.dtype),
        device_map=args.device,
        trust_remote_code=True,
    ).eval()
    separator_id = tokenizer.encode("<extra_0>")[0]

    output_path = Path(
        args.output
        or f"prm_scores_{args.model.split('/')[-1].lower().replace('-', '_')}.jsonl"
    )
    done = set()
    if output_path.exists():
        with output_path.open(encoding="utf-8") as handle:
            done = {json.loads(line)["step_id"] for line in handle}
        print(f"resuming: {len(done)} steps already scored")

    with Path(args.input).open(encoding="utf-8") as handle, output_path.open(
        "a", encoding="utf-8"
    ) as sink:
        for line in handle:
            record = json.loads(line)
            if record["step_id"] in done:
                continue
            conversation = build_conversation(record)
            input_ids = tokenizer.apply_chat_template(
                conversation, tokenize=True, return_tensors="pt"
            ).to(model.device)
            with torch.no_grad():
                outputs = model(input_ids=input_ids)
            token_mask = (input_ids == separator_id)
            logits = outputs[0][token_mask]
            probabilities = torch.softmax(logits.float(), dim=-1)[:, 1].tolist()
            if len(probabilities) != len(record["steps"]):
                status = "step_count_mismatch"
            else:
                status = "ok"
            sink.write(
                json.dumps(
                    {
                        "step_id": record["step_id"],
                        "model": args.model,
                        "status": status,
                        "step_scores": probabilities,
                        "target_index": record["target_index"],
                        "target_score": (
                            probabilities[record["target_index"]]
                            if record["target_index"] < len(probabilities)
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
