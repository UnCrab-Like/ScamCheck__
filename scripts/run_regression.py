import json
import os
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from app import baseline_risk_level, risk_rank


def main() -> int:
    path = os.path.join(PROJECT_ROOT, "data", "regression_cases.json")
    with open(path, encoding="utf-8") as file:
        cases = json.load(file)

    rows = []
    passed = 0
    for index, case in enumerate(cases, start=1):
        expected = case["label"]
        predicted = baseline_risk_level(case["text"])
        ok = predicted == expected
        dangerous_downgrade = expected == "Nguy hiểm" and risk_rank(predicted) < risk_rank(expected)
        if ok:
            passed += 1
        rows.append((index, expected, predicted, "FAIL" if dangerous_downgrade else "OK" if ok else "MISS", case["text"][:52]))

    print("| # | Expected | Predicted | Result | Text |")
    print("|---|----------|-----------|--------|------|")
    for row in rows:
        print(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} |")
    print(f"\nPassed: {passed}/{len(cases)}")

    return 0 if passed == len(cases) else 1


if __name__ == "__main__":
    raise SystemExit(main())
