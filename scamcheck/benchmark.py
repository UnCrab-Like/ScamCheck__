"""Offline benchmark runner for the deterministic ScamCheck safety layer."""

from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any

from scamcheck.analysis import baseline_risk_level


def load_offline_benchmark() -> dict[str, Any]:
    path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "data",
        "offline_benchmark.json",
    )
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def run_offline_benchmark() -> dict[str, Any]:
    """Score deterministic analysis without network access or AI usage."""
    benchmark = load_offline_benchmark()
    results = []
    category_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"correct": 0, "total": 0}
    )

    for case in benchmark["cases"]:
        predicted = baseline_risk_level(case["text"])
        correct = predicted == case["expected_risk"]
        category = case["category"]
        category_totals[category]["total"] += 1
        category_totals[category]["correct"] += int(correct)
        results.append(
            {
                "id": case["id"],
                "category": category,
                "expected_risk": case["expected_risk"],
                "predicted_risk": predicted,
                "correct": correct,
                "text": case["text"],
            }
        )

    total = len(results)
    correct = sum(item["correct"] for item in results)
    categories = [
        {
            "category": category,
            **counts,
            "percentage": round(100 * counts["correct"] / counts["total"], 1),
        }
        for category, counts in sorted(category_totals.items())
    ]
    return {
        "name": benchmark["name"],
        "version": benchmark["version"],
        "score": correct,
        "total": total,
        "percentage": round(100 * correct / total, 1) if total else 0,
        "ai_calls_used": 0,
        "categories": categories,
        "cases": results,
    }
