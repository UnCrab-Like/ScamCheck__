#!/usr/bin/env python3
"""Print ScamCheck's categorized deterministic benchmark score."""

from __future__ import annotations

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from scamcheck.benchmark import run_offline_benchmark


def main() -> int:
    result = run_offline_benchmark()
    print(f"ScamCheck score: {result['score']}/{result['total']} ({result['percentage']}%)")
    print(f"AI calls used: {result['ai_calls_used']}")
    print("\nScores by category:")
    for category in result["categories"]:
        print(
            f"  {category['category']}: "
            f"{category['correct']}/{category['total']} ({category['percentage']}%)"
        )

    failures = [case for case in result["cases"] if not case["correct"]]
    if failures:
        print("\nIncorrect predictions:")
        for case in failures:
            print(
                f"  [{case['category']}] {case['id']}: "
                f"predicted {case['predicted_risk']}, "
                f"expected {case['expected_risk']}"
            )
        return 1

    print("\nAll benchmark predictions were correct.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
