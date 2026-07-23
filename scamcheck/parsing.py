"""Defensive parsers for structured Gemini responses."""

from __future__ import annotations

import json
from typing import Any, Callable

from scamcheck.analysis import RISK_LEVELS
from scamcheck.config import DEFAULT_RESULT


def parse_gemini_result(raw: Any) -> dict[str, Any]:
    """Return a valid detective result even when Gemini output is malformed."""
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return DEFAULT_RESULT.copy()
    if not isinstance(data, dict):
        return DEFAULT_RESULT.copy()

    risk_level = data.get("risk_level")
    if risk_level not in RISK_LEVELS:
        risk_level = DEFAULT_RESULT["risk_level"]

    indicators = []
    raw_indicators = data.get("indicators", [])
    if not isinstance(raw_indicators, list):
        raw_indicators = []
    for item in raw_indicators:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label", "")).strip()
        explanation = str(item.get("explanation", "")).strip()
        quote = str(item.get("quote", "")).strip()
        if label or explanation or quote:
            indicators.append(
                {
                    "label": label or "Dấu hiệu chưa đặt tên",
                    "quote": quote[:300],
                    "explanation": explanation or "Cần kiểm tra thêm.",
                }
            )
    if not indicators:
        indicators = list(DEFAULT_RESULT["indicators"])

    raw_actions = data.get("actions", [])
    if not isinstance(raw_actions, list):
        raw_actions = []
    actions = [str(action).strip() for action in raw_actions if str(action).strip()]
    actions = (actions + list(DEFAULT_RESULT["actions"]))[:3]
    summary = str(data.get("summary", "")).strip() or DEFAULT_RESULT["summary"]
    return {
        "risk_level": risk_level,
        "indicators": indicators[:5],
        "actions": actions,
        "summary": summary[:500],
    }


def split_sentences(text: str) -> list[str]:
    """Split short AI explanations without requiring a language model library."""
    text = " ".join(str(text).split())
    sentences = []
    current = ""
    for char in text:
        current += char
        if char in ".!?。":
            sentence = current.strip()
            if sentence:
                sentences.append(sentence)
            current = ""
    if current.strip():
        sentences.append(current.strip())
    return sentences


def parse_psychology_result(raw: Any) -> dict[str, str]:
    """Enforce the psychologist's voice and two-to-three-sentence limit."""
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"explanation": raw}
    if not isinstance(data, dict):
        data = {}

    explanation = str(data.get("explanation", "")).strip()
    sentences = split_sentences(explanation)
    if len(sentences) < 2:
        sentences = [
            "Cô thấy tin này đang dùng cảm giác gấp gáp để làm bác phản ứng nhanh.",
            "Bác cứ dừng lại một chút và kiểm tra qua kênh chính thức trước khi làm theo.",
        ]
    explanation = " ".join(sentences[:3])
    if "bác" not in explanation.lower():
        explanation = f"Bác lưu ý, {explanation[0].lower()}{explanation[1:]}" if explanation else ""
    if "cô" not in explanation.lower():
        explanation = f"Cô thấy {explanation[0].lower()}{explanation[1:]}" if explanation else ""
    return {"explanation": explanation}


def parse_psychology_chat_result(raw: Any) -> dict[str, str]:
    """Normalize a chat reply and provide a safe fallback question."""
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {"reply": raw}
    reply = str(data.get("reply", "")).strip() if isinstance(data, dict) else ""
    if not reply:
        reply = "Cô chưa hiểu rõ chuyện vừa xảy ra. Bác cho cô biết mình đã bấm link, nhập thông tin hay chuyển tiền chưa nhé."
    return {"reply": " ".join(reply.split())[:1200]}


def parse_responder_result(
    raw: Any, sanitizer: Callable[[list[dict[str, str]]], list[dict[str, str]]]
) -> dict[str, Any]:
    """Parse responder steps and pass them through the caller's sanitizer."""
    data = raw
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            data = {}
    if not isinstance(data, dict):
        data = {}
    steps = data.get("steps", [])
    if not isinstance(steps, list):
        steps = []
    return {"steps": sanitizer(steps[:6])}
