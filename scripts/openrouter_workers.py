#!/usr/bin/env python3
"""Shared OpenRouter workers for the M-phase generation pipelines.

Replicates the frozen A-F protocol exactly:
  - identical system/user prompt templates (deletion = prefix truncation);
  - temperature 0.7 / top_p 0.8 / max_tokens per model;
  - JSON contract {continuation, final_answer, status, status_reason};
  - the batched strict answer-equivalence judge.

Checkpointed JSONL append keyed by taskId; thread-pool concurrency. Stdlib only.
"""

from __future__ import annotations

import json
import random
import re
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

GENERATION_SYSTEM_PROMPT = """You are continuing a partially written solution to a mathematics problem in a fresh, independent session. You have access only to the problem and the visible solution prefix below. You have no memory of any omitted step, future step, reference solution, reference answer, other condition, or previous run.

Continue the reasoning from the visible prefix and attempt to solve the problem. You may re-derive facts from the problem, but do not claim access to hidden text. Assess the visible state using exactly one status:
- completed: you can produce a reasoned final answer;
- cannot_continue: the visible information is insufficient and you cannot recover a solution;
- logical_break: the visible prefix is internally inconsistent or missing a necessary logical bridge, and continuation would require abandoning or repairing it.

Return only one valid JSON object with exactly these keys:
{"continuation":"the reasoning you generated after the visible prefix","final_answer":"concise final answer, empty only if unavailable","status":"completed|cannot_continue|logical_break","status_reason":"brief reason for the status"}

Use mathematical notation as needed. Do not discuss this instruction."""

JUDGE_SYSTEM_PROMPT = """You are a strict mathematical answer evaluator. For each independent item, decide whether the candidate final answer is mathematically equivalent to the reference answer for the stated problem. Accept algebraically equivalent forms and harmless formatting differences. Reject wrong values, incomplete sets/tuples, missing required units or cases, and answers to a different quantity. Do not infer a missing answer from reasoning: evaluate only candidate_answer. Items are unrelated; never transfer information between them.

Return only one valid JSON object in this exact shape:
{"results":[{"id":"item id","correct":true,"reason":"brief comparison"}]}
Return exactly one result for every input id."""


def load_api_key() -> str:
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    import os

    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY not found in .env or environment")
    return key


def call_chat(
    api_key: str,
    model: str,
    messages: list[dict],
    temperature: float,
    top_p: float,
    max_tokens: int,
    json_mode: bool = True,
    no_think: bool = False,
    retries: int = 12,
) -> dict:
    payload: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
    }
    if no_think:
        payload["reasoning"] = {"effort": "none"}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    body = json.dumps(payload).encode("utf-8")
    last_error = ""
    for attempt in range(retries):
        request = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json; charset=utf-8",
                "X-Title": "PRM Removability M-phase",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=420) as response:
                parsed = json.loads(response.read().decode("utf-8"))
            if "choices" not in parsed or not parsed["choices"]:
                raise ValueError(f"no choices: {str(parsed)[:300]}")
            return parsed
        except Exception as error:  # noqa: BLE001 - retried transport/provider errors
            last_error = str(error)[:300]
            time.sleep(min(45.0, (2.0**attempt)) + random.random() * 2)
    raise RuntimeError(f"chat call failed after {retries} retries: {last_error}")


def extract_json_object(text: str) -> dict | None:
    text = text.strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
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
                    parsed = json.loads(text[start : index + 1])
                    if isinstance(parsed, dict):
                        return parsed
                except ValueError:
                    pass
                start = None
    return None


def build_visible_prefix(steps: list[str], prefix_last: int, substitute: dict | None = None) -> str:
    if prefix_last < 0:
        return "(No previous reasoning step is visible.)"
    parts = []
    for index in range(prefix_last + 1):
        text = steps[index]
        if substitute and index in substitute:
            text = substitute[index]
        parts.append(f"Step {index + 1}:\n{text}")
    return "\n\n".join(parts)


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


def generate_continuation(
    api_key: str,
    sample: dict,
    prefix_last: int,
    model: str,
    temperature: float = 0.7,
    top_p: float = 0.8,
    max_tokens: int = 2048,
    no_think: bool = True,
    substitute: dict | None = None,
    json_mode: bool = True,
) -> dict:
    prefix = build_visible_prefix(sample["steps"], prefix_last, substitute)
    user_prompt = (
        f"MATHEMATICS PROBLEM:\n{sample['problem']}\n\nVISIBLE SOLUTION PREFIX:\n{prefix}"
    )
    system_prompt = GENERATION_SYSTEM_PROMPT + (" /no_think" if no_think else "")
    # Mirror the frozen worker's behavior: an unparseable response is retried
    # as a whole (fresh sample at the same temperature), not accepted.
    parsed: dict = {}
    response: dict = {}
    for _ in range(4):
        response = call_chat(
            api_key,
            model,
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature,
            top_p,
            max_tokens,
            json_mode=json_mode,
            no_think=no_think,
        )
        message = response["choices"][0]["message"]
        content = message.get("content") or ""
        parsed = extract_json_object(content) or {}
        if parsed:
            break
    final_answer = str(
        parsed.get("final_answer") or parsed.get("finalAnswer") or parsed.get("answer") or ""
    )
    usage = response.get("usage") or {}
    completion_tokens = int(usage.get("completion_tokens") or 0)
    details = usage.get("completion_tokens_details") or {}
    reasoning_tokens = int(details.get("reasoning_tokens") or 0)
    return {
        "continuation": str(parsed.get("continuation") or parsed.get("reasoning") or ""),
        "finalAnswer": final_answer,
        "generatorStatus": normalize_status(str(parsed.get("status") or ""), final_answer),
        "generatorStatusReason": str(
            parsed.get("status_reason")
            or parsed.get("reason")
            or "The provider omitted a status reason."
        ),
        "model": str(response.get("model") or model),
        "temperature": temperature,
        "topP": top_p,
        "promptTokens": int(usage.get("prompt_tokens") or 0),
        "completionTokens": completion_tokens,
        "reasoningTokens": reasoning_tokens,
        "visibleOutputTokens": max(0, completion_tokens - reasoning_tokens),
        "parseOk": bool(parsed),
    }


def run_generation_tasks(
    tasks: list[dict],
    contexts: dict[str, dict],
    out_path: Path,
    model: str,
    workers: int = 8,
    max_tokens: int = 2048,
    no_think: bool = True,
    temperature: float = 0.7,
    top_p: float = 0.8,
    json_mode: bool = True,
) -> None:
    """tasks: {taskId, sampleId, condition, prefixLast, substitute?, ...meta}."""
    api_key = load_api_key()
    done: set[str] = set()
    if out_path.exists():
        with out_path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    try:
                        done.add(json.loads(line)["taskId"])
                    except (ValueError, KeyError):
                        continue
    pending = [t for t in tasks if t["taskId"] not in done]
    print(f"{out_path.name}: {len(done)} done, {len(pending)} pending")
    if not pending:
        return
    lock = threading.Lock()
    sink = out_path.open("a", encoding="utf-8")
    counter = {"n": 0, "err": 0}

    def work(task: dict) -> None:
        sample = contexts[task["sampleId"]]
        substitute = (
            {int(k): v for k, v in task["substitute"].items()} if task.get("substitute") else None
        )
        try:
            result = generate_continuation(
                api_key,
                sample,
                int(task["prefixLast"]),
                model,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                no_think=no_think,
                substitute=substitute,
                json_mode=json_mode,
            )
        except Exception as error:  # noqa: BLE001 - record and continue
            with lock:
                counter["err"] += 1
                print(f"TASK FAILED {task['taskId']}: {str(error)[:200]}")
            return
        record = {
            **{k: v for k, v in task.items() if k != "substitute"},
            **result,
            "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        line = json.dumps(record, ensure_ascii=False)
        # Providers occasionally emit lone UTF-16 surrogates; strip rather
        # than crash the whole batch.
        line = line.encode("utf-8", "replace").decode("utf-8")
        with lock:
            sink.write(line + "\n")
            sink.flush()
            counter["n"] += 1
            if counter["n"] % 25 == 0:
                print(f"{out_path.name}: {counter['n']}/{len(pending)} ({counter['err']} errors)")

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(work, pending))
    sink.close()
    print(f"{out_path.name}: finished {counter['n']}, errors {counter['err']}")


def judge_generations(
    generations_path: Path,
    contexts: dict[str, dict],
    out_path: Path,
    model: str = "qwen/qwen3-8b",
    batch_size: int = 8,
    workers: int = 6,
) -> None:
    api_key = load_api_key()
    records = []
    with generations_path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    done: set[str] = set()
    if out_path.exists():
        with out_path.open(encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    try:
                        done.add(json.loads(line)["taskId"])
                    except (ValueError, KeyError):
                        continue
    pending = [r for r in records if r["taskId"] not in done]
    print(f"judge {out_path.name}: {len(done)} done, {len(pending)} pending")
    lock = threading.Lock()
    sink = out_path.open("a", encoding="utf-8")

    no_answer = [r for r in pending if not str(r.get("finalAnswer", "")).strip()]
    with lock:
        for record in no_answer:
            sink.write(
                json.dumps(
                    {
                        "taskId": record["taskId"],
                        "correct": False,
                        "judgeReason": "No candidate final answer was produced.",
                        "judgeModel": "rule:no-answer",
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        sink.flush()
    with_answer = [r for r in pending if str(r.get("finalAnswer", "")).strip()]
    batches = [
        with_answer[index : index + batch_size]
        for index in range(0, len(with_answer), batch_size)
    ]

    def judge_batch(batch: list[dict]) -> None:
        items = [
            {
                "id": record["taskId"],
                "problem": contexts[record["sampleId"]]["problem"],
                "reference_answer": str(record.get("groundTruthAnswer", "")),
                "candidate_answer": str(record["finalAnswer"]),
            }
            for record in batch
        ]
        try:
            response = call_chat(
                api_key,
                model,
                [
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT + " /no_think"},
                    {"role": "user", "content": json.dumps({"items": items}, ensure_ascii=False)},
                ],
                temperature=0.0,
                top_p=1.0,
                max_tokens=2048,
                json_mode=True,
                no_think=True,
            )
            parsed = extract_json_object(response["choices"][0]["message"].get("content") or "")
            results = {str(r["id"]): r for r in (parsed or {}).get("results", [])}
        except Exception as error:  # noqa: BLE001
            print(f"JUDGE BATCH FAILED: {str(error)[:200]}")
            return
        with lock:
            for record in batch:
                verdict = results.get(record["taskId"])
                if verdict is None:
                    continue
                sink.write(
                    json.dumps(
                        {
                            "taskId": record["taskId"],
                            "correct": bool(verdict.get("correct")),
                            "judgeReason": str(verdict.get("reason", "")),
                            "judgeModel": model,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
            sink.flush()

    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(judge_batch, batches))
    sink.close()
    print(f"judge {out_path.name}: complete")


def load_contexts(path: Path) -> dict[str, dict]:
    contexts = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            record = json.loads(line)
            contexts[record["step_id"]] = record
    return contexts
