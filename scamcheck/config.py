"""Central configuration and Gemini response schemas."""

from __future__ import annotations

import os
import re

from scamcheck.analysis import RISK_LEVELS


def load_local_env() -> None:
    """Load an uncommitted project .env before deriving configuration values."""
    project_root = os.path.dirname(os.path.dirname(__file__))
    env_path = os.path.join(project_root, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()

MAX_AI_CALLS_PER_SESSION = 20
AI_TIMEOUT_SECONDS = 6
REQUEST_BUDGET_SECONDS = 20
MAX_INPUT_CHARS = 5000
RESULT_CACHE_LIMIT = 20
PHONE_RE = re.compile(r"(?<!\d)(?:\+?84[-.\s]?)?(?:0?\d[-.\s]?){2,12}\d(?!\d)")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)
GEMINI_STREAM_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:streamGenerateContent?alt=sse"
)

RESCUE_OPTIONS = {
    "clicked_link": "Bác mới bấm đường dẫn hoặc mở tệp nhưng chưa nhập thông tin.",
    "shared_info": "Bác đã nhập thông tin cá nhân, mật khẩu, OTP hoặc ảnh giấy tờ.",
    "sent_money": "Bác đã chuyển tiền hoặc cung cấp thông tin thẻ/tài khoản.",
    "installed_app": "Bác đã cài ứng dụng lạ, tệp APK/EXE hoặc cấp quyền điều khiển.",
}

DEFAULT_RESULT = {
    "risk_level": "Nghi ngờ",
    "indicators": [
        {
            "label": "Chưa có đủ dữ liệu tin cậy",
            "quote": "",
            "explanation": "Kết quả AI không đúng định dạng, nên ứng dụng dùng kết quả mặc định an toàn hơn.",
        }
    ],
    "actions": [
        "Không bấm liên kết hoặc tải tệp đính kèm.",
        "Xác minh lại qua kênh chính thức trước khi trả lời.",
        "Không chuyển tiền, mã OTP hoặc thông tin cá nhân.",
    ],
    "summary": "Cần kiểm tra thủ công thêm.",
}

RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "risk_level": {
            "type": "string",
            "enum": list(RISK_LEVELS),
            "description": "Mức rủi ro tổng thể của tin nhắn.",
        },
        "indicators": {
            "type": "array",
            "minItems": 1,
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "quote": {
                        "type": "string",
                        "description": "Đoạn trích nguyên văn tìm thấy trong tin gốc.",
                    },
                    "explanation": {"type": "string"},
                },
                "required": ["label", "quote", "explanation"],
            },
        },
        "actions": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {"type": "string"},
        },
        "summary": {"type": "string"},
    },
    "required": ["risk_level", "indicators", "actions", "summary"],
}

PSYCHOLOGY_SCHEMA = {
    "type": "object",
    "properties": {
        "explanation": {
            "type": "string",
            "description": "2 tới 3 câu tiếng Việt, xưng cô và gọi người dùng là bác.",
        }
    },
    "required": ["explanation"],
}

PSYCHOLOGY_CHAT_SCHEMA = {
    "type": "object",
    "properties": {"reply": {"type": "string"}},
    "required": ["reply"],
}

RESPONDER_SCHEMA = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "minItems": 3,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "say": {"type": "string"},
                },
                "required": ["action", "say"],
            },
        }
    },
    "required": ["steps"],
}
