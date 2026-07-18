import argparse
import asyncio
import json
import os
import statistics
import sys
import time


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from app import build_prompt, call_gemini_json, enforce_risk_floor, parse_gemini_result, RESULT_SCHEMA, risk_rank


async def evaluate_case(case):
    started = time.monotonic()
    raw = await call_gemini_json(
        build_prompt(case["text"]),
        RESULT_SCHEMA,
        parse_gemini_result,
        started + 30,
        max_retries=2,
    )
    result = enforce_risk_floor(raw, case["text"])
    return result["risk_level"], time.monotonic() - started


async def main_async(limit, concurrency):
    path = os.path.join(PROJECT_ROOT, "data", "evaluation_60.json")
    with open(path, encoding="utf-8") as file:
        cases = json.load(file)[:limit]

    correct = 0
    valid = 0
    dangerous_downgrades = 0
    latencies = []
    semaphore = asyncio.Semaphore(concurrency)

    async def run_numbered(index, case):
        async with semaphore:
            return index, case, await evaluate_case(case)

    tasks = [asyncio.create_task(run_numbered(index, case)) for index, case in enumerate(cases, 1)]
    for task in asyncio.as_completed(tasks):
        try:
            index, case, (predicted, elapsed) = await task
            valid += 1
            correct += predicted == case["label"]
            latencies.append(elapsed)
            if case["label"] == "Nguy hiểm" and risk_rank(predicted) < risk_rank("Nguy hiểm"):
                dangerous_downgrades += 1
            print(f"{index:02d}/{len(cases)} expected={case['label']} predicted={predicted} time={elapsed:.2f}s")
        except Exception as exc:
            status = getattr(exc, "code", "")
            detail = "quota/rate limit" if status == 429 else type(exc).__name__
            print(f"ERROR {detail}")

    print("\nLive Gemini evidence")
    print(f"Valid structure: {valid}/{len(cases)} ({valid / len(cases):.2%})")
    print(f"Accuracy: {correct}/{len(cases)} ({correct / len(cases):.2%})")
    print(f"Dangerous downgrades: {dangerous_downgrades}")
    if latencies:
        print(f"Median latency: {statistics.median(latencies):.2f}s")
        print(f"Maximum latency: {max(latencies):.2f}s")
    return 0 if valid >= len(cases) * 0.9 and dangerous_downgrades == 0 else 1


def main():
    parser = argparse.ArgumentParser(description="Measure live Gemini structure, accuracy, safety, and latency.")
    parser.add_argument("--limit", type=int, default=10, choices=range(1, 61), metavar="1-60")
    parser.add_argument("--concurrency", type=int, default=2, choices=range(1, 6), metavar="1-5")
    args = parser.parse_args()
    if not os.getenv("GEMINI_API_KEY"):
        print("Set GEMINI_API_KEY before running the live evaluation.", file=sys.stderr)
        return 2
    return asyncio.run(main_async(args.limit, args.concurrency))


if __name__ == "__main__":
    raise SystemExit(main())
