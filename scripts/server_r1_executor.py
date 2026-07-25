#!/usr/bin/env python3
"""Self-contained executor for the long-CoT replication (runs ON the GPU box).

Reads m10_prompt_tasks.jsonl (taskId + messages + metadata), sends each task
to a local vLLM OpenAI endpoint serving DeepSeek-R1-Distill-Qwen-14B, parses
the frozen JSON generation contract from the post-<think> text (up to 4
whole-request retries, mirroring the frozen workers), and appends results to
m10_generations.jsonl (checkpointed by taskId). Stdlib only.

    ~/vllm-venv/bin/python server_r1_executor.py --workers 24
"""

from __future__ import annotations

import argparse
import json
import re
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

URLS = [f"http://127.0.0.1:{port}/v1/chat/completions" for port in (8113, 8114, 8115, 8116)]
MODEL = "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B"


def extract_json_object(text: str):
    text = text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except ValueError:
        pass
    depth = 0
    start = None
    for index, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(text[start : index + 1])
                except ValueError:
                    start = None
    return None


def normalize_status(status: str, final_answer: str) -> str:
    normalized = (status or "").strip().lower().replace("-", "_").replace(" ", "_")
    if normalized in {"completed", "cannot_continue", "logical_break"}:
        return normalized
    if "logical" in normalized or "break" in normalized:
        return "logical_break"
    if "cannot" in normalized or "unable" in normalized:
        return "cannot_continue"
    if "complete" in normalized or final_answer.strip():
        return "completed"
    return "cannot_continue"


def call_local(url, messages, temperature, top_p, max_tokens, timeout=900):
    payload = json.dumps(
        {
            "model": MODEL,
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
        }
    ).encode("utf-8")
    last = None
    for attempt in range(5):
        try:
            request = urllib.request.Request(
                url, data=payload, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as error:  # noqa: BLE001
            last = error
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"request failed after retries: {last}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default="m10_prompt_tasks.jsonl")
    parser.add_argument("--output", default="m10_generations.jsonl")
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--max-tokens", type=int, default=12288)
    args = parser.parse_args()

    tasks = [
        json.loads(line)
        for line in Path(args.tasks).open(encoding="utf-8")
        if line.strip()
    ]
    out_path = Path(args.output)
    done = set()
    if out_path.exists():
        with out_path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    done.add(json.loads(line)["taskId"])
    pending = [t for t in tasks if t["taskId"] not in done]
    print(f"{len(done)} done, {len(pending)} pending", flush=True)

    lock = threading.Lock()
    sink = out_path.open("a", encoding="utf-8")
    counter = {"n": 0, "err": 0}

    def work(task: dict) -> None:
        messages = [
            {"role": "system", "content": task["system"]},
            {"role": "user", "content": task["user"]},
        ]
        parsed = None
        raw_chars = 0
        attempts = 0
        try:
            for attempts in range(1, 5):
                url = URLS[hash(task["taskId"]) % len(URLS)]
                response = call_local(url, messages, 0.7, 0.8, args.max_tokens)
                text = response["choices"][0]["message"].get("content") or ""
                reasoning = response["choices"][0]["message"].get("reasoning_content") or ""
                raw_chars = len(text) + len(reasoning)
                parsed = extract_json_object(text)
                if isinstance(parsed, dict) and "status" in parsed:
                    break
                parsed = None
        except Exception as error:  # noqa: BLE001
            with lock:
                counter["err"] += 1
                print(f"TASK ERROR {task['taskId']}: {str(error)[:150]}", flush=True)
            return
        record = {
            key: value
            for key, value in task.items()
            if key not in ("system", "user")
        }
        if parsed is None:
            record.update(
                {"continuation": "", "finalAnswer": "", "status": "cannot_continue",
                 "statusReason": "Unparseable after 4 attempts.", "parseAttempts": attempts,
                 "rawChars": raw_chars, "generatorModel": MODEL}
            )
        else:
            final_answer = str(parsed.get("final_answer", "") or "")
            record.update(
                {
                    "continuation": str(parsed.get("continuation", "") or ""),
                    "finalAnswer": final_answer,
                    "status": normalize_status(str(parsed.get("status", "") or ""), final_answer),
                    "statusReason": str(
                        parsed.get("status_reason", parsed.get("reason", "")) or ""
                    ),
                    "parseAttempts": attempts,
                    "rawChars": raw_chars,
                    "generatorModel": MODEL,
                }
            )
        with lock:
            sink.write(json.dumps(record, ensure_ascii=False) + "\n")
            sink.flush()
            counter["n"] += 1
            if counter["n"] % 50 == 0:
                print(f"progress {counter['n']}/{len(pending)} err={counter['err']}", flush=True)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, pending))
    print(f"finished: {counter['n']} written, {counter['err']} errors", flush=True)


if __name__ == "__main__":
    main()
