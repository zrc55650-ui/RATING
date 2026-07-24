#!/usr/bin/env python3
"""StepRem test-split evaluation.

Input: a CSV with columns step_id, danger_score, benefit_score where higher
danger_score means "more likely to destroy a correct run if deleted" and
higher benefit_score means "more likely to rescue a wrong run".

Usage: python evaluate.py predictions.csv steprem_test_hidden.csv
"""
import csv
import sys


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def auprc(labels, scores):
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    positives = sum(labels)
    if not positives:
        return float("nan")
    tp = 0
    total = 0.0
    for rank, index in enumerate(order, 1):
        if labels[index]:
            tp += 1
            total += tp / rank
    return total / positives


def main():
    predictions = {r["step_id"]: r for r in read(sys.argv[1])}
    hidden = read(sys.argv[2])
    rows = [r for r in hidden if r["step_id"] in predictions]
    if len(rows) < len(hidden):
        print(f"WARNING: {len(hidden) - len(rows)} test steps missing predictions")
    danger_labels = [1 if int(r["correct_to_wrong_count"]) > 0 else 0 for r in rows]
    benefit_labels = [1 if int(r["wrong_to_correct_count"]) > 0 else 0 for r in rows]
    danger_scores = [float(predictions[r["step_id"]]["danger_score"]) for r in rows]
    benefit_scores = [float(predictions[r["step_id"]]["benefit_score"]) for r in rows]
    print("steps evaluated:", len(rows))
    print("danger AUPRC:", round(auprc(danger_labels, danger_scores), 4),
          "| base rate:", round(sum(danger_labels) / len(rows), 4))
    print("benefit AUPRC:", round(auprc(benefit_labels, benefit_scores), 4),
          "| base rate:", round(sum(benefit_labels) / len(rows), 4))


if __name__ == "__main__":
    main()
