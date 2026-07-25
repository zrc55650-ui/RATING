#!/usr/bin/env python3
"""M1 adapter: score all 600 trajectories with the RLHFlow trained PRM.

Checkpoint: RLHFlow/Llama3.1-8B-PRM-Deepseek-Data (Math-Shepherd-style
training on DeepSeek-generated data). Per the model card, each step is a user
turn (the first carries the problem) answered by an assistant "+"; the step
score is P('+') vs P('-') at the assistant position.

Usage (GPU box):
    python score_with_rlhflow_prm.py --input prm_scoring_input.jsonl

Output schema matches score_with_qwen_prm.py.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="RLHFlow/Llama3.1-8B-PRM-Deepseek-Data")
    parser.add_argument("--input", default="prm_scoring_input.jsonl")
    parser.add_argument("--output", default="prm_scores_llama31_8b_prm_deepseek.jsonl")
    parser.add_argument("--device", default="cuda")
    args = parser.parse_args()

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model, torch_dtype=torch.bfloat16, device_map=args.device
    ).eval()
    plus_id = tokenizer.encode("+", add_special_tokens=False)[-1]
    minus_id = tokenizer.encode("-", add_special_tokens=False)[-1]

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
            step_scores = []
            conversation = []
            ok = True
            for i, step in enumerate(record["steps"]):
                content = f"{record['problem']} {step}" if i == 0 else step
                conversation.append({"role": "user", "content": content})
                conversation.append({"role": "assistant", "content": "+"})
                input_ids = tokenizer.apply_chat_template(
                    conversation, return_tensors="pt"
                )[:, -4096:].to(model.device)
                positions = (input_ids[0] == plus_id).nonzero(as_tuple=True)[0]
                if len(positions) == 0:
                    ok = False
                    break
                pos = positions[-1].item()
                with torch.no_grad():
                    logits = model(input_ids).logits[0, pos - 1, [plus_id, minus_id]]
                step_scores.append(
                    torch.softmax(logits.float(), dim=-1)[0].item()
                )
            status = "ok" if ok and len(step_scores) == len(record["steps"]) else "parse_failure"
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
                            if status == "ok" and target_index < len(step_scores)
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
