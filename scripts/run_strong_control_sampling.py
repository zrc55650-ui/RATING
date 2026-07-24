#!/usr/bin/env python3
"""Workstream M4: sample the 240-step strong-control subset.

Groups (disjoint, 80 each, per ACL-Main plan section 8.2):
  A  negative_anchor      rating = -1 AND human-calibrated Harmful
  B  stable_correct       control 4/4 correct, not in A (dangerous-deletion candidates)
  C  neutral_comparison   rating in {0, 1}, control < 4/4, not in A

Within each group: position-bin quotas (early/middle/late), preference for
placebo-eligible steps (condition C2 needs a matched placebo), deterministic
stable-hash ordering. Outputs a sampling manifest, balance sanity checks and
the C3 paraphrase input file. Stdlib only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from analysis_common import (
    ROOT,
    as_float,
    as_int,
    fmt,
    mean,
    read_csv,
    sample_sd,
    stable_hash,
    write_csv,
)

OUT_DIR = ROOT / "workstream_M4_strong_controls"
GROUP_SIZE = 80
POSITION_BINS = ["early", "middle", "late"]
NEW_RUNS_PER_CONDITION = 4


def load_steps() -> list[dict]:
    rows = read_csv(ROOT / "data" / "master_step_table.csv")
    steps = []
    for row in rows:
        steps.append(
            {
                "step_id": row["step_id"],
                "problem_id": row["problem_id"],
                "rating": as_int(row["prm_rating"]),
                "type_hc": row["step_type_human_calibrated"].strip().lower(),
                "type_initial": row["step_type_initial"].strip().lower(),
                "position_bin": row["position_bin"],
                "position_ratio": as_float(row["position_ratio"]),
                "target_tokens": as_int(row["target_tokens"]),
                "prefix_tokens": as_int(row["prefix_tokens"]),
                "control_correct_count": as_int(row["control_correct_count"]),
                "control_stability": row["control_stability"],
                "placebo_eligible": row["placebo_eligible"].strip() == "1",
                "target_effect": as_float(row["target_effect"]),
                "c2w": as_int(row["correct_to_wrong_count"]),
                "w2c": as_int(row["wrong_to_correct_count"]),
                "target_step_text": row["target_step_text"],
            }
        )
    return steps


def group_of(step: dict) -> str | None:
    if step["rating"] == -1 and step["type_hc"] == "harmful":
        return "negative_anchor"
    if step["control_correct_count"] == 4:
        return "stable_correct"
    if step["rating"] in (0, 1):
        return "neutral_comparison"
    return None


def quota_sample(pool: list[dict], size: int) -> list[dict]:
    """Fill position-bin quotas, preferring placebo-eligible steps."""
    base, extra = divmod(size, len(POSITION_BINS))
    quotas = {
        bin_name: base + (1 if index < extra else 0)
        for index, bin_name in enumerate(POSITION_BINS)
    }
    selected: list[dict] = []
    chosen_ids: set[str] = set()
    for bin_name in POSITION_BINS:
        candidates = sorted(
            (s for s in pool if s["position_bin"] == bin_name),
            key=lambda s: (not s["placebo_eligible"], stable_hash(s["step_id"])),
        )
        take = candidates[: quotas[bin_name]]
        selected.extend(take)
        chosen_ids.update(s["step_id"] for s in take)
    if len(selected) < size:
        leftovers = sorted(
            (s for s in pool if s["step_id"] not in chosen_ids),
            key=lambda s: (not s["placebo_eligible"], stable_hash(s["step_id"])),
        )
        selected.extend(leftovers[: size - len(selected)])
    return selected


def smd(left: list[float], right: list[float]) -> float:
    pooled = math.sqrt((sample_sd(left) ** 2 + sample_sd(right) ** 2) / 2.0)
    if pooled == 0:
        return 0.0
    return (mean(left) - mean(right)) / pooled


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    steps = load_steps()

    pools: dict[str, list[dict]] = {"negative_anchor": [], "stable_correct": [], "neutral_comparison": []}
    for step in steps:
        group = group_of(step)
        if group:
            pools[group].append(step)

    sampled: dict[str, list[dict]] = {
        group: quota_sample(pool, GROUP_SIZE) for group, pool in pools.items()
    }

    # --- sanity checks -----------------------------------------------------
    problems: list[str] = []
    all_ids = [s["step_id"] for group in sampled.values() for s in group]
    if len(all_ids) != 3 * GROUP_SIZE:
        problems.append(f"expected {3 * GROUP_SIZE} steps, got {len(all_ids)}")
    if len(set(all_ids)) != len(all_ids):
        problems.append("duplicate step_ids across groups")
    for group, rows in sampled.items():
        if len(rows) != GROUP_SIZE:
            problems.append(f"group {group} has {len(rows)} steps")
        for s in rows:
            if group_of(s) != group:
                problems.append(f"step {s['step_id']} misassigned to {group}")

    manifest = []
    for group, rows in sampled.items():
        for s in rows:
            manifest.append(
                {
                    "step_id": s["step_id"],
                    "problem_id": s["problem_id"],
                    "strong_control_group": group,
                    "prm_rating": s["rating"],
                    "step_type_human_calibrated": s["type_hc"],
                    "position_bin": s["position_bin"],
                    "position_ratio": fmt(s["position_ratio"], 4),
                    "target_tokens": s["target_tokens"],
                    "prefix_tokens": s["prefix_tokens"],
                    "control_correct_count": s["control_correct_count"],
                    "placebo_eligible": int(s["placebo_eligible"]),
                    "reuse_c0_c1_runs": NEW_RUNS_PER_CONDITION,
                    "new_c2_placebo_runs": NEW_RUNS_PER_CONDITION,
                    "new_c3_paraphrase_runs": NEW_RUNS_PER_CONDITION,
                }
            )
    manifest.sort(key=lambda r: (r["strong_control_group"], r["step_id"]))
    write_csv(OUT_DIR / "strong_control_sampling_manifest.csv", manifest)

    paraphrase_inputs = []
    for group, rows in sampled.items():
        for s in rows:
            paraphrase_inputs.append(
                {
                    "step_id": s["step_id"],
                    "strong_control_group": group,
                    "target_step_text": s["target_step_text"],
                    "instruction": (
                        "Paraphrase the given math reasoning step. Preserve its exact "
                        "mathematical meaning and conclusion (including any errors). Do not "
                        "add or remove information. Keep approximately the same length."
                    ),
                }
            )
    with (OUT_DIR / "strong_control_paraphrase_inputs.jsonl").open("w", encoding="utf-8") as handle:
        for row in sorted(paraphrase_inputs, key=lambda r: r["step_id"]):
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    balance_rows = []
    covariates = ["position_ratio", "target_tokens", "prefix_tokens"]
    group_names = list(sampled)
    for covariate in covariates:
        row = {"covariate": covariate}
        for group in group_names:
            values = [float(s[covariate]) for s in sampled[group]]
            row[f"{group}_mean"] = fmt(mean(values), 2)
            row[f"{group}_sd"] = fmt(sample_sd(values), 2)
        for i, left in enumerate(group_names):
            for right in group_names[i + 1 :]:
                value = smd(
                    [float(s[covariate]) for s in sampled[left]],
                    [float(s[covariate]) for s in sampled[right]],
                )
                row[f"smd_{left}_vs_{right}"] = fmt(value, 3)
        balance_rows.append(row)
    write_csv(OUT_DIR / "strong_control_balance.csv", balance_rows)

    summary = {
        "group_sizes": {group: len(rows) for group, rows in sampled.items()},
        "pool_sizes": {group: len(pool) for group, pool in pools.items()},
        "position_bin_counts": {
            group: {
                bin_name: sum(1 for s in rows if s["position_bin"] == bin_name)
                for bin_name in POSITION_BINS
            }
            for group, rows in sampled.items()
        },
        "placebo_eligible_counts": {
            group: sum(1 for s in rows if s["placebo_eligible"])
            for group, rows in sampled.items()
        },
        "rating_by_group": {
            group: {
                str(r): sum(1 for s in rows if s["rating"] == r) for r in (-1, 0, 1)
            }
            for group, rows in sampled.items()
        },
        "new_generation_budget": {
            "c2_placebo_runs": 3 * GROUP_SIZE * NEW_RUNS_PER_CONDITION,
            "c3_paraphrase_runs": 3 * GROUP_SIZE * NEW_RUNS_PER_CONDITION,
            "total_new_runs": 3 * GROUP_SIZE * NEW_RUNS_PER_CONDITION * 2,
            "paraphrase_candidates": 3 * GROUP_SIZE,
        },
        "sanity_check_problems": problems,
        "sanity_check_passed": not problems,
    }
    (OUT_DIR / "strong_control_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    lines = [
        "# Workstream M4:Strong-Control 240-Step 采样",
        "",
        "按 ACL Main 计划 8.2 节从冻结的 600-step 主表抽取三个互斥组(各 80 步):",
        "",
        "- `negative_anchor`:rating = -1 且 human-calibrated Harmful;",
        "- `stable_correct`:control 4/4 correct(dangerous deletion 候选),不含 A 组;",
        "- `neutral_comparison`:rating 0/1 且 control 非 4/4,不含 A 组。",
        "",
        "组内按 position bin 配额(~27/27/26)平衡,优先选择 placebo-eligible steps",
        "(C2 条件需要 position-and-length-matched placebo),stable hash 确定性排序,可复现。",
        "",
        "## 采样结果",
        "",
        f"- 组大小:{summary['group_sizes']}",
        f"- 采样池:{summary['pool_sizes']}",
        f"- position 分布:{json.dumps(summary['position_bin_counts'], ensure_ascii=False)}",
        f"- placebo eligible:{summary['placebo_eligible_counts']}",
        f"- sanity check:{'PASS' if summary['sanity_check_passed'] else 'FAIL: ' + '; '.join(problems)}",
        "",
        "## 四条件设计与新生成预算",
        "",
        "| 条件 | 说明 | Runs | 来源 |",
        "|---|---|---:|---|",
        "| C0 Control | 保留原 target step | 4 | 复用已有 runs |",
        "| C1 Target deletion | 删除 target step | 4 | 复用已有 runs |",
        f"| C2 Matched placebo | 位置+长度匹配的其他 step 删除 | {NEW_RUNS_PER_CONDITION} | 新生成 |",
        f"| C3 Semantic-preserving paraphrase | 独立模型保义改写 | {NEW_RUNS_PER_CONDITION} | 新生成 |",
        "",
        f"新增 continuation runs:240 x 4 x 2 = **{summary['new_generation_budget']['total_new_runs']}**;",
        f"paraphrase 生成:**{summary['new_generation_budget']['paraphrase_candidates']}** 条(1 candidate/step,失败再补)。",
        "",
        "## 输出文件",
        "",
        "- `strong_control_sampling_manifest.csv`:240 步采样清单;",
        "- `strong_control_balance.csv`:三组间 position/step length/prefix length 的 SMD;",
        "- `strong_control_paraphrase_inputs.jsonl`:C3 paraphrase 生成输入;",
        "- `strong_control_summary.json`:参数、配额与 sanity check 结果。",
        "",
        "## 已知边界",
        "",
        "- `negative_anchor` 组 target step 天然长于 `stable_correct` 组(target_tokens SMD ~0.7),",
        "  这是两组定义带来的池子属性,不是采样缺陷;主 estimand 是同一 step 内 C0-C3 的",
        "  within-step 对比,组间长度差异不进入该对比。跨组比较时按组分层报告,不做直接合并。",
        "",
        "## 后续动作",
        "",
        "1. C3 paraphrase 用独立模型(非 Qwen3-8B)生成,人工抽查至少 120 条语义保真;",
        "2. C2 placebo 复用 `select_placebo_steps.py` 的匹配逻辑,对 89 个不可匹配步骤记录排除;",
        "3. 新 runs 完成后按 C1-C2(target-specific)、C1-C3(semantic-content)分解机制。",
    ]
    (OUT_DIR / "strong_control_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Workstream M4 strong-control sampling generated:", OUT_DIR)
    print("Sanity check:", "PASS" if not problems else problems)


if __name__ == "__main__":
    main()
