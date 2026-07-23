"""Verified hotline access, phone allow-listing, and crisis fallbacks."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from scamcheck.config import PHONE_RE

def load_hotlines() -> dict[str, Any]:
    """Load the repository's verified hotline allow-list."""
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "hotlines_verified.json")
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def normalize_phone(phone: str) -> str:
    """Remove formatting so phone numbers can be compared reliably."""
    return re.sub(r"\D", "", phone)


def allowed_phone_numbers() -> set[str]:
    """Build accepted local and country-code variants of verified numbers."""
    numbers = set()
    for contact in load_hotlines()["contacts"]:
        normalized = normalize_phone(contact["phone"])
        numbers.add(normalized)
        if normalized.startswith("0"):
            numbers.add(f"84{normalized[1:]}")
    return numbers


def hotline_contacts(contact_type: str | None = None) -> list[dict[str, str]]:
    """Return all verified contacts or only contacts of one type."""
    contacts = load_hotlines()["contacts"]
    if contact_type:
        contacts = [item for item in contacts if item["type"] == contact_type]
    return contacts


def sanitize_phone_hallucinations(text: str) -> str:
    """Block any displayed phone number that is not in the verified table."""
    allowed = allowed_phone_numbers()

    def replace(match: re.Match) -> str:
        """Keep an allow-listed number or replace it with a visible warning."""
        raw = match.group(0)
        normalized = normalize_phone(raw)
        if normalized in allowed or (normalized.startswith("84") and normalized in allowed):
            return raw
        return "[số đã bị chặn]"

    return PHONE_RE.sub(replace, text)


def sanitize_responder_steps(steps: list[dict[str, str]]) -> list[dict[str, str]]:
    """Normalize responder steps and apply phone filtering to every field."""
    clean = []
    for step in steps:
        clean.append(
            {
                "action": sanitize_phone_hallucinations(str(step.get("action", "")).strip()),
                "say": sanitize_phone_hallucinations(str(step.get("say", "")).strip()),
            }
        )
    return [item for item in clean if item["action"] and item["say"]]



def fallback_rescue_steps(situation: str) -> list[dict[str, str]]:
    """Build a deterministic emergency plan when the responder AI is unavailable."""
    banks = hotline_contacts("bank")
    police = next(item for item in hotline_contacts("police") if item["id"] == "police_113")
    ais_156 = next(item for item in hotline_contacts("information_security") if item["id"] == "ais_156")
    ais_5656 = next(item for item in hotline_contacts("information_security") if item["id"] == "ais_5656")
    bank_list = ", ".join(f"{bank['name']} {bank['phone']}" for bank in banks[:5])
    common = [
        {
            "action": "Dừng trả lời tin nhắn và chụp lại màn hình làm bằng chứng.",
            "say": "Tôi cần giữ nguyên bằng chứng tin nhắn này để ngân hàng hoặc công an kiểm tra.",
        },
        {
            "action": f"Phản ánh lừa đảo tới {ais_156['name']} {ais_156['phone']} hoặc nhắn LD [nguồn] [nội dung] gửi {ais_5656['phone']}.",
            "say": "Tôi muốn phản ánh một nội dung nghi lừa đảo trực tuyến.",
        },
    ]
    if situation == "clicked_link":
        specific = [
            {
                "action": "Thoát trang vừa mở, không nhập thêm thông tin, đổi mật khẩu nếu đã đăng nhập ở trang đó.",
                "say": "Tôi đã bấm nhầm link nghi giả mạo nhưng chưa chuyển tiền.",
            }
        ]
    elif situation == "shared_info":
        specific = [
            {
                "action": f"Gọi ngay ngân hàng đang dùng để khóa dịch vụ. Một số tổng đài phổ biến: {bank_list}.",
                "say": "Tôi nghi đã lộ thông tin đăng nhập hoặc OTP, xin khóa dịch vụ và kiểm tra giao dịch ngay.",
            }
        ]
    elif situation == "sent_money":
        specific = [
            {
                "action": f"Gọi ngay ngân hàng đang dùng để yêu cầu tra soát/khẩn cấp giữ giao dịch nếu còn có thể. Một số tổng đài: {bank_list}.",
                "say": "Tôi vừa chuyển tiền do bị lừa, xin lập yêu cầu tra soát khẩn cấp và hướng dẫn phong tỏa nếu còn kịp.",
            },
            {
                "action": f"Nếu đang bị đe dọa hoặc mất tiền lớn, gọi {police['name']} {police['phone']} hoặc đến công an gần nhất.",
                "say": "Tôi cần trình báo việc bị lừa chuyển tiền và có bằng chứng giao dịch.",
            },
        ]
    else:
        specific = [
            {
                "action": "Ngắt mạng thiết bị, không mở app ngân hàng trên thiết bị đã cài app lạ.",
                "say": "Tôi nghi thiết bị đã cài ứng dụng độc hại, cần khóa dịch vụ ngân hàng trước.",
            },
            {
                "action": f"Dùng điện thoại khác gọi ngân hàng đang dùng để khóa dịch vụ. Một số tổng đài: {bank_list}.",
                "say": "Thiết bị của tôi có thể bị điều khiển, xin khóa tài khoản/thẻ và kiểm tra giao dịch.",
            },
        ]
    return sanitize_responder_steps([common[0], *specific, common[1]])
