#!/usr/bin/env python3
"""Match ProcessBench problems to source-dataset gold answers.

Sources: GSM8K (openai/gsm8k), MATH (DigitalLearningGmbH/MATH-lighteval),
OlympiadBench (Hothan/OlympiadBench OE_TO_maths_en_COMP), Omni-MATH
(KbsdJames/Omni-MATH). Fallback: extract the final answer from a sibling
trajectory of the same problem whose final_answer_correct is True.

Run with: uv run --with datasets python fetch_gold_answers.py
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_boxed(text: str) -> str | None:
    marker = "\\boxed{"
    start = text.rfind(marker)
    if start < 0:
        return None
    index = start + len(marker)
    depth = 1
    out = []
    while index < len(text) and depth:
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                break
        out.append(char)
        index += 1
    return "".join(out).strip() or None


def load_source_maps() -> dict[str, dict[str, str]]:
    from datasets import load_dataset

    maps: dict[str, dict[str, str]] = {}

    gsm = load_dataset("openai/gsm8k", "main", split="test")
    maps["gsm8k"] = {
        norm(r["question"]): r["answer"].split("####")[-1].strip() for r in gsm
    }
    print("gsm8k gold:", len(maps["gsm8k"]))

    math_ds = load_dataset("DigitalLearningGmbH/MATH-lighteval", "default", split="test")
    math_map = {}
    for r in math_ds:
        answer = extract_boxed(r["solution"])
        if answer:
            math_map[norm(r["problem"])] = answer
    maps["math"] = math_map
    print("math gold:", len(math_map))

    try:
        oly = load_dataset("Hothan/OlympiadBench", "OE_TO_maths_en_COMP", split="train")
        maps["olympiadbench"] = {
            norm(r["question"]): (r["final_answer"][0] if r["final_answer"] else "")
            for r in oly
            if r.get("final_answer")
        }
        print("olympiadbench gold:", len(maps["olympiadbench"]))
    except Exception as error:  # noqa: BLE001
        print("olympiadbench source failed:", str(error)[:200])
        maps["olympiadbench"] = {}

    try:
        omni = load_dataset("KbsdJames/Omni-MATH", split="test")
        maps["omnimath"] = {norm(r["problem"]): r["answer"] for r in omni if r.get("answer")}
        print("omnimath gold:", len(maps["omnimath"]))
    except Exception as error:  # noqa: BLE001
        print("omnimath source failed:", str(error)[:200])
        maps["omnimath"] = {}
    return maps


def sibling_gold(records: list[dict]) -> dict[str, str]:
    by_problem = defaultdict(list)
    for r in records:
        by_problem[norm(r["problem"])].append(r)
    result = {}
    for problem, group in by_problem.items():
        for r in group:
            if not r["final_answer_correct"]:
                continue
            final_step = r["steps"][-1] if r["steps"] else ""
            answer = extract_boxed(final_step)
            if not answer:
                match = re.search(
                    r"(?:answer is|answer:)\s*\$?([^.\n$]+)", final_step, re.IGNORECASE
                )
                answer = match.group(1).strip() if match else None
            if answer:
                result[problem] = answer
                break
    return result


def main() -> None:
    maps = load_source_maps()
    out = {}
    stats = {}
    for name in ("gsm8k", "math", "olympiadbench", "omnimath"):
        records = json.load((DATA / f"{name}.json").open())
        source_map = maps.get(name, {})
        siblings = sibling_gold(records)
        matched_source = matched_sibling = missing = 0
        for r in records:
            key = f"{name}|{r['id']}"
            problem = norm(r["problem"])
            if problem in source_map:
                out[key] = {"gold": source_map[problem], "source": "dataset"}
                matched_source += 1
            elif problem in siblings:
                out[key] = {"gold": siblings[problem], "source": "sibling_trajectory"}
                matched_sibling += 1
            else:
                missing += 1
        stats[name] = {
            "records": len(records),
            "matched_source": matched_source,
            "matched_sibling": matched_sibling,
            "missing": missing,
        }
        print(name, stats[name])
    (HERE / "gold_answers.json").write_text(
        json.dumps({"answers": out, "stats": stats}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print("total gold:", len(out))


if __name__ == "__main__":
    main()
