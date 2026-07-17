import json
import os
import sys
from collections import Counter


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, PROJECT_ROOT)

from app import RISK_LEVELS, baseline_risk_level


def legacy_classifier(text: str) -> str:
    lowered = text.lower()
    if "otp" in lowered or "chuyen tien" in lowered or ".apk" in lowered:
        return "Nguy hiểm"
    if "http" in lowered or "trung thuong" in lowered or "xac minh" in lowered:
        return "Nghi ngờ"
    return "An toàn"


def load_cases(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def evaluate(cases: list[dict[str, str]], classifier) -> dict[str, object]:
    matrix = {expected: Counter() for expected in RISK_LEVELS}
    misses = []
    covered = 0
    for case in cases:
        expected = case["label"]
        predicted = classifier(case["text"])
        if predicted in RISK_LEVELS:
            covered += 1
        matrix[expected][predicted] += 1
        if predicted != expected:
            misses.append({**case, "predicted": predicted})
    return {
        "accuracy": (len(cases) - len(misses)) / len(cases),
        "coverage": covered / len(cases),
        "matrix": matrix,
        "misses": misses,
    }


def print_matrix(matrix: dict[str, Counter]) -> None:
    print("| Expected \\ Predicted | An toàn | Nghi ngờ | Nguy hiểm |")
    print("|---|---:|---:|---:|")
    for expected in RISK_LEVELS:
        row = matrix[expected]
        print(f"| {expected} | {row['An toàn']} | {row['Nghi ngờ']} | {row['Nguy hiểm']} |")


def print_report(name: str, result: dict[str, object]) -> None:
    print(f"\n## {name}")
    print(f"Accuracy: {result['accuracy']:.2%}")
    print(f"Coverage: {result['coverage']:.2%}")
    print_matrix(result["matrix"])
    misses = result["misses"]
    if misses:
        print("\nMisses:")
        for miss in misses[:10]:
            print(f"- expected={miss['label']} predicted={miss['predicted']} reason={miss['reason']} text={miss['text'][:80]}")


def weakness_summary(misses: list[dict[str, str]]) -> list[str]:
    defaults = [
        "Tin phí nhỏ như phí lưu kho có thể nằm giữa Nghi ngờ và Nguy hiểm, cần thêm dữ liệu thật để đặt ngưỡng.",
        "Giải link rút gọn thật phụ thuộc mạng và có thể không chạy trong môi trường offline.",
        "Chưa kiểm tra được nội dung ảnh/chụp màn hình, chỉ xử lý văn bản.",
    ]
    if not misses:
        return defaults
    text = " ".join(miss["text"].lower() for miss in misses)
    weaknesses = []
    if "otp" in text:
        weaknesses.append("Một số câu nhắc OTP theo hướng bảo mật có thể bị hiểu quá rủi ro nếu thiếu ngữ cảnh.")
    if "shipper" in text or "giao" in text:
        weaknesses.append("Tin giao hàng thật và giả dễ lẫn nếu không có link hoặc yêu cầu phí rõ ràng.")
    if "ngan hang" in text or "bank" in text:
        weaknesses.append("Tên tổ chức trong câu kể bình thường có thể tạo false positive nếu rule quá rộng.")
    for item in defaults:
        if item not in weaknesses:
            weaknesses.append(item)
    return weaknesses[:3]


def main() -> int:
    cases = load_cases(os.path.join(PROJECT_ROOT, "data", "evaluation_60.json"))
    before = evaluate(cases, legacy_classifier)
    after = evaluate(cases, baseline_risk_level)
    print_report("Before rule/domain improvements", before)
    print_report("After rule/domain improvements", after)
    print("\nImprovement:")
    print(f"- Accuracy: {before['accuracy']:.2%} -> {after['accuracy']:.2%}")
    print(f"- Coverage: {before['coverage']:.2%} -> {after['coverage']:.2%}")
    print("\nWeaknesses:")
    for item in weakness_summary(after["misses"]):
        print(f"- {item}")
    return 0 if after["accuracy"] >= before["accuracy"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
