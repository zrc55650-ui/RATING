#!/usr/bin/env python3
"""Dependency-free statistical helpers for the removability analyses."""

from __future__ import annotations

import csv
import hashlib
import math
import random
from pathlib import Path
from typing import Callable, Iterable, Sequence


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
BUILD = ROOT / "build"
BUILD.mkdir(exist_ok=True)
SEED = 20260723
BOOTSTRAP_REPLICATES = 5000


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(
    path: str | Path,
    rows: Iterable[dict],
    fieldnames: Sequence[str] | None = None,
) -> None:
    materialized = list(rows)
    if fieldnames is None:
        fieldnames = list(materialized[0]) if materialized else []
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(materialized)


def as_float(value: object, default: float = math.nan) -> float:
    try:
        if value is None or str(value).strip() == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: object, default: int = 0) -> int:
    try:
        if value is None or str(value).strip() == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def mean(values: Iterable[float]) -> float:
    vals = [x for x in values if not math.isnan(x)]
    return sum(vals) / len(vals) if vals else math.nan


def sample_sd(values: Iterable[float]) -> float:
    vals = [x for x in values if not math.isnan(x)]
    if len(vals) < 2:
        return 0.0
    center = sum(vals) / len(vals)
    return math.sqrt(sum((x - center) ** 2 for x in vals) / (len(vals) - 1))


def quantile(values: Iterable[float], probability: float) -> float:
    vals = sorted(x for x in values if not math.isnan(x))
    if not vals:
        return math.nan
    if len(vals) == 1:
        return vals[0]
    position = (len(vals) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return vals[lower]
    weight = position - lower
    return vals[lower] * (1.0 - weight) + vals[upper] * weight


def median(values: Iterable[float]) -> float:
    return quantile(values, 0.5)


def percentile_interval(
    values: Iterable[float], lower: float = 0.025, upper: float = 0.975
) -> tuple[float, float]:
    vals = list(values)
    return quantile(vals, lower), quantile(vals, upper)


def stable_hash(text: str, seed: int = SEED) -> int:
    digest = hashlib.sha256(f"{seed}|{text}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def grouped_fold_assignment(
    rows: Sequence[dict[str, str]],
    group_key: str,
    folds: int = 5,
    seed: int = SEED,
) -> dict[str, int]:
    """Assign whole groups to folds while balancing row counts deterministically."""
    group_sizes: dict[str, int] = {}
    for row in rows:
        group = row[group_key]
        group_sizes[group] = group_sizes.get(group, 0) + 1
    ordered = sorted(
        group_sizes,
        key=lambda group: (-group_sizes[group], stable_hash(group, seed)),
    )
    fold_sizes = [0] * folds
    assignment: dict[str, int] = {}
    for group in ordered:
        fold = min(range(folds), key=lambda candidate: (fold_sizes[candidate], candidate))
        assignment[group] = fold
        fold_sizes[fold] += group_sizes[group]
    return assignment


def bootstrap_group_difference(
    left: Sequence[dict],
    right: Sequence[dict],
    statistic: Callable[[Sequence[dict]], float],
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = SEED,
) -> tuple[float, float, float]:
    rng = random.Random(seed)
    estimate = statistic(left) - statistic(right)
    draws: list[float] = []
    for _ in range(replicates):
        left_draw = [left[rng.randrange(len(left))] for _ in left]
        right_draw = [right[rng.randrange(len(right))] for _ in right]
        draws.append(statistic(left_draw) - statistic(right_draw))
    lower, upper = percentile_interval(draws)
    return estimate, lower, upper


def permutation_pvalue(
    values: Sequence,
    left_size: int,
    statistic: Callable[[Sequence, Sequence], float],
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = SEED,
) -> float:
    rng = random.Random(seed)
    observed = abs(statistic(values[:left_size], values[left_size:]))
    working = list(values)
    extreme = 0
    for _ in range(replicates):
        rng.shuffle(working)
        candidate = abs(statistic(working[:left_size], working[left_size:]))
        if candidate >= observed - 1e-15:
            extreme += 1
    return (extreme + 1) / (replicates + 1)


def solve_linear_system(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> list[float]:
    """Gaussian elimination with partial pivoting."""
    n = len(vector)
    augmented = [list(matrix[row]) + [vector[row]] for row in range(n)]
    for column in range(n):
        pivot = max(range(column, n), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            augmented[pivot][column] = 1e-12
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        for item in range(column, n + 1):
            augmented[column][item] /= pivot_value
        for row in range(n):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0:
                continue
            for item in range(column, n + 1):
                augmented[row][item] -= factor * augmented[column][item]
    return [augmented[row][n] for row in range(n)]


def sigmoid(value: float) -> float:
    if value >= 0:
        exponent = math.exp(-min(value, 700.0))
        return 1.0 / (1.0 + exponent)
    exponent = math.exp(max(value, -700.0))
    return exponent / (1.0 + exponent)


def fit_logistic_irls(
    x_rows: Sequence[Sequence[float]],
    outcomes: Sequence[int],
    l2: float = 1.0,
    max_iter: int = 80,
    tolerance: float = 1e-8,
) -> list[float]:
    """Fit a small L2-regularized logistic model without external libraries."""
    width = len(x_rows[0]) + 1
    design = [[1.0, *row] for row in x_rows]
    coefficients = [0.0] * width
    positives = sum(outcomes)
    negatives = len(outcomes) - positives
    positive_weight = len(outcomes) / (2.0 * positives) if positives else 1.0
    negative_weight = len(outcomes) / (2.0 * negatives) if negatives else 1.0

    for _ in range(max_iter):
        information = [[0.0] * width for _ in range(width)]
        gradient = [0.0] * width
        for row, outcome in zip(design, outcomes):
            probability = sigmoid(sum(c * value for c, value in zip(coefficients, row)))
            class_weight = positive_weight if outcome else negative_weight
            variance = max(probability * (1.0 - probability), 1e-7) * class_weight
            residual = (outcome - probability) * class_weight
            for first in range(width):
                gradient[first] += row[first] * residual
                for second in range(first, width):
                    information[first][second] += row[first] * row[second] * variance
        for first in range(width):
            for second in range(first):
                information[first][second] = information[second][first]
        for index in range(1, width):
            gradient[index] -= l2 * coefficients[index]
            information[index][index] += l2
        information[0][0] += 1e-8
        update = solve_linear_system(information, gradient)
        coefficients = [old + change for old, change in zip(coefficients, update)]
        if max(abs(change) for change in update) < tolerance:
            break
    return coefficients


def predict_logistic(
    coefficients: Sequence[float], x_rows: Sequence[Sequence[float]]
) -> list[float]:
    predictions = []
    for row in x_rows:
        value = coefficients[0] + sum(
            coefficient * feature for coefficient, feature in zip(coefficients[1:], row)
        )
        predictions.append(sigmoid(value))
    return predictions


def roc_auc(outcomes: Sequence[int], scores: Sequence[float]) -> float:
    positives = sum(outcomes)
    negatives = len(outcomes) - positives
    if positives == 0 or negatives == 0:
        return math.nan
    order = sorted(range(len(scores)), key=lambda index: scores[index])
    rank_sum = 0.0
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and scores[order[end]] == scores[order[start]]:
            end += 1
        average_rank = (start + 1 + end) / 2.0
        rank_sum += average_rank * sum(outcomes[order[index]] for index in range(start, end))
        start = end
    return (rank_sum - positives * (positives + 1) / 2.0) / (positives * negatives)


def average_precision(outcomes: Sequence[int], scores: Sequence[float]) -> float:
    positives = sum(outcomes)
    if positives == 0:
        return math.nan
    order = sorted(range(len(scores)), key=lambda index: (-scores[index], index))
    true_positives = 0
    precision_sum = 0.0
    for rank, index in enumerate(order, start=1):
        if outcomes[index]:
            true_positives += 1
            precision_sum += true_positives / rank
    return precision_sum / positives


def brier_score(outcomes: Sequence[int], scores: Sequence[float]) -> float:
    return mean((outcome - score) ** 2 for outcome, score in zip(outcomes, scores))


def expected_calibration_error(
    outcomes: Sequence[int], scores: Sequence[float], bins: int = 10
) -> float:
    total = len(outcomes)
    result = 0.0
    for bin_index in range(bins):
        lower = bin_index / bins
        upper = (bin_index + 1) / bins
        members = [
            index
            for index, score in enumerate(scores)
            if lower <= score < upper or (bin_index == bins - 1 and score == 1.0)
        ]
        if not members:
            continue
        observed = mean(outcomes[index] for index in members)
        predicted = mean(scores[index] for index in members)
        result += len(members) / total * abs(observed - predicted)
    return result


def specificity_at_half(outcomes: Sequence[int], scores: Sequence[float]) -> float:
    negatives = [index for index, outcome in enumerate(outcomes) if not outcome]
    if not negatives:
        return math.nan
    true_negatives = sum(scores[index] < 0.5 for index in negatives)
    return true_negatives / len(negatives)


def precision_coverage(
    outcomes: Sequence[int], scores: Sequence[float], target_precision: float
) -> float:
    order = sorted(range(len(scores)), key=lambda index: (-scores[index], index))
    positives = 0
    best = 0
    for rank, index in enumerate(order, start=1):
        positives += outcomes[index]
        if positives / rank >= target_precision:
            best = rank
    return best / len(outcomes)


def metric_bundle(outcomes: Sequence[int], scores: Sequence[float]) -> dict[str, float]:
    return {
        "auroc": roc_auc(outcomes, scores),
        "auprc": average_precision(outcomes, scores),
        "brier": brier_score(outcomes, scores),
        "ece_10bin": expected_calibration_error(outcomes, scores),
        "specificity_at_0.5": specificity_at_half(outcomes, scores),
        "coverage_at_90pct_precision": precision_coverage(outcomes, scores, 0.90),
        "coverage_at_95pct_precision": precision_coverage(outcomes, scores, 0.95),
    }


def fold_bootstrap_interval(
    fold_values: Sequence[float],
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = SEED,
) -> tuple[float, float]:
    rng = random.Random(seed)
    draws = [
        mean(fold_values[rng.randrange(len(fold_values))] for _ in fold_values)
        for _ in range(replicates)
    ]
    return percentile_interval(draws)


def fmt(value: float, digits: int = 3) -> str:
    if math.isnan(value):
        return ""
    return f"{value:.{digits}f}"


def fmt_pp(value: float, digits: int = 2) -> str:
    if math.isnan(value):
        return ""
    return f"{value * 100:+.{digits}f}"


def xml_escape(text: object) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_svg(path: str | Path, width: int, height: int, body: str) -> None:
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">\n'
        "<style>"
        "text{font-family:Arial,'Microsoft YaHei',sans-serif;fill:#172033}"
        ".small{font-size:12px}.label{font-size:14px}.title{font-size:20px;font-weight:700}"
        ".axis{stroke:#8791a5;stroke-width:1}.grid{stroke:#dfe3eb;stroke-width:1}"
        "</style>\n"
        f'<rect width="{width}" height="{height}" fill="white"/>\n{body}\n</svg>\n'
    )
    Path(path).write_text(svg, encoding="utf-8")
