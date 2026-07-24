#!/usr/bin/env python3
"""M1 adapter: score target steps with a generative / LLM-judge style PRM.

Covers the second PRM class in the plan (reasoning PRMs such as R-PRM or
"Process Reward Models That Think"). Two backends:

  --backend hf         local checkpoint via transformers (GPU box)
  --backend openrouter chat API (reads OPENROUTER_API_KEY); use a reasoning
                       model as a prompted process judge. This is an
                       LLM-as-PRM approximation and must be labeled as such
                       in the paper, distinct from trained PRM checkpoints.

Scores only the target step (cheaper than full-trajectory scoring); the
prompt shows problem + prefix + target step and asks for a 0-100 correctness
score in JSON. Stdlib only for the openrouter backend. Checkpointed output.

Usage:
    export OPENROUTER_API_KEY=...
    python score_with_generative_prm.py --backend openrouter \
        --model deepseek/deepseek-r1-distill-qwen-14b \
        --input prm_scoring_input.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.request
from pathlib import Path

JUDGE_PROMPT = """You are a process reward model for mathematical reasoning.

Problem:
{problem}

Reasoning so far (steps before the step under evaluation):
{prefix}

Step under evaluation:
{target}

Assess ONLY the step under evaluation: is it mathematically correct and a
valid continuation of the reasoning so far? Ignore whether it is useful or
efficient; judge correctness. Reply with JSON only:
{{"score": <integer 0-100, probability the step is correct>, "verdict": "correct" | "incorrect" | "unsure"}}"""


def call_openrouter(model: str, prompt: str, api_key: str, retries: int = 5) -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 2000,
    }
    request = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=180) as response:
                body = json.loads(response.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"]
        except Exception as error:  # noqa: BLE001 - retry on any transport error
            if attempt == retries - 1:
                raise
            time.sleep(2**attempt)
    raise RuntimeError("unreachable")


def parse_score(text: str) -> dict:
    match = re.search(r"\{[^{}]*\"score\"[^{}]*\}", text, re.DOTALL)
    if not match:
        return {"score": None, "verdict": "unparsed", "raw": text[-400:]}
    try:
        parsed = json.loads(match.group(0))
        return {
            "score": float(parsed.get("score")) / 100.0,
            "verdict": parsed.get("verdict", ""),
        }
    except (ValueError, TypeError):
        return {"score": None, "verdict": "unparsed", "raw": text[-400:]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["openrouter", "hf"], default="openrouter")
    parser.add_argument("--model", required=True)
    parser.add_argument("--input", default="prm_scoring_input.jsonl")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    slug = re.sub(r"[^a-z0-9]+", "_", args.model.lower())
    output_path = Path(args.output or f"prm_scores_{slug}.jsonl")
    done = set()
    if output_path.exists():
        with output_path.open(encoding="utf-8") as handle:
            done = {json.loads(line)["step_id"] for line in handle}
        print(f"resuming: {len(done)} steps already scored")

    if args.backend == "openrouter":
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        if not api_key:
            env_path = Path(__file__).resolve().parent.parent / ".env"
            if env_path.exists():
                for line in env_path.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("OPENROUTER_API_KEY="):
                        api_key = line.split("=", 1)[1].strip().strip('"').strip("'")
        else:
            api_key = api_key.strip().strip('"').strip("'")
        if not api_key:
            raise SystemExit("OPENROUTER_API_KEY is not set")
    else:
        raise SystemExit(
            "hf backend: load the released R-PRM / ThinkPRM checkpoint per its model "
            "card on a GPU box, then mirror the openrouter loop with local generate()."
        )

    with Path(args.input).open(encoding="utf-8") as handle, output_path.open(
        "a", encoding="utf-8"
    ) as sink:
        for line in handle:
            record = json.loads(line)
            if record["step_id"] in done:
                continue
            prompt = JUDGE_PROMPT.format(
                problem=record["problem"],
                prefix="\n".join(record["steps"][: record["target_index"]]) or "(none)",
                target=record["steps"][record["target_index"]],
            )
            reply = call_openrouter(args.model, prompt, api_key)
            result = parse_score(reply)
            sink.write(
                json.dumps(
                    {
                        "step_id": record["step_id"],
                        "model": args.model,
                        "backend": args.backend,
                        "prm_class": "generative_llm_judge",
                        "target_index": record["target_index"],
                        "target_score": result.get("score"),
                        "verdict": result.get("verdict"),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            sink.flush()
    print("done ->", output_path)


if __name__ == "__main__":
    main()
