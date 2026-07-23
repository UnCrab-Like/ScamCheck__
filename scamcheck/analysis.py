"""Deterministic URL and message-risk analysis.

This module contains the pure, reusable safety checks.  Keeping them independent
from Flask makes them easy to test and reuse from command-line evaluation tools.
"""

from __future__ import annotations

import re
from typing import Any, Callable
from urllib.parse import urlparse

import requests

RISK_LEVELS = ("An toàn", "Nghi ngờ", "Nguy hiểm")

URL_RE = re.compile(
    r"(?<![\w@])((?:https?://|www\.)[^\s<>'\"]+|(?:[a-z0-9-]+\.)+(?:com|vn|net|org|info|io|me|co|xyz|top|shop|site|online|app|live|cc|ly|gl|to|is|ai)\b[^\s<>'\"]*)",
    re.IGNORECASE,
)
SHORTENER_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "cutt.ly",
    "shorturl.at", "rebrand.ly", "ow.ly", "s.id",
}
OFFICIAL_DOMAINS = {
    "vietcombank.com.vn": "Vietcombank", "vcb.com.vn": "Vietcombank",
    "bidv.com.vn": "BIDV", "vietinbank.vn": "VietinBank",
    "techcombank.com": "Techcombank", "mbbank.com.vn": "MB Bank",
    "vpbank.com.vn": "VPBank", "tpb.vn": "TPBank", "acb.com.vn": "ACB",
    "sacombank.com.vn": "Sacombank", "vnpay.vn": "VNPay", "momo.vn": "MoMo",
    "zalopay.vn": "ZaloPay", "ghn.vn": "Giao Hang Nhanh",
    "ghtk.vn": "Giao Hang Tiet Kiem", "viettelpost.com.vn": "Viettel Post",
    "vnpost.vn": "VNPost", "dichvucong.gov.vn": "Dich vu cong",
}
HOMOGLYPHS = str.maketrans({
    "0": "o", "1": "l", "3": "e", "5": "s", "а": "a", "е": "e",
    "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i",
})

RULES = (
    (r"\b(otp|mã otp|ma otp|mã xác thực|ma xac thuc|verification code)\b", "Yêu cầu mã xác thực", "Không cung cấp mã OTP hoặc mã xác thực cho người khác."),
    (r"(chuyển tiền|chuyen tien|chuyển khoản|chuyen khoan|ck ngay|nộp tiền|nop tien|đóng phí|dong phi|phí hồ sơ|phi ho so|phí lưu kho|phi luu kho)", "Yêu cầu chuyển khoản/đóng phí", "Tin yêu cầu chuyển tiền trước khi xác minh là dấu hiệu rủi ro cao."),
    (r"\b\d{9,14}\b.*(ngân hàng|ngan hang|stk|số tài khoản|so tai khoan)", "Có số tài khoản lạ", "Tin có số tài khoản để nhận tiền cần được xác minh qua kênh chính thức."),
    (r"(ngay lập tức|ngay lap tuc|trong \d+ phút|trong \d+ phut|khẩn cấp|khan cap|hôm nay|hom nay)", "Tạo áp lực gấp gáp", "Cụm từ gấp gáp làm người đọc khó kiểm tra lại."),
    (r"(\.apk|\.exe|cài app|cai app|cài đặt|cai dat|tải tệp|tai tep)", "Yêu cầu tải/cài tệp lạ", "Tệp hoặc ứng dụng ngoài nguồn chính thức có thể chứa mã độc."),
    (r"(công an|cong an|viện kiểm sát|vien kiem sat|tòa án|toa an)", "Giả danh cơ quan chức năng", "Cơ quan chức năng không yêu cầu xử lý vụ việc qua link hoặc chuyển khoản trong tin nhắn."),
    (r"(bị khóa|bi khoa|khóa tài khoản|khoa tai khoan)", "Đe dọa khóa tài khoản/hồ sơ", "Đe dọa khóa tài khoản thường được dùng để ép người nhận làm theo ngay."),
    (r"(căn cước|can cuoc|cccd|chứng minh nhân dân|chung minh nhan dan)", "Yêu cầu giấy tờ cá nhân", "Gửi giấy tờ cá nhân qua chat/link lạ có thể bị lợi dụng."),
    (r"(link chat|nhóm riêng|nhom rieng|lợi nhuận cao|loi nhuan cao)", "Kéo sang kênh riêng hoặc đầu tư mơ hồ", "Kẻ gian thường kéo người nhận ra khỏi kênh chính thức để thao túng tiếp."),
    (r"(tieu de:|tiêu đề:).*(than bai:|thân bài:).*(bam link|bấm link|nhan qua|nhận quà)", "Tiêu đề và thân mâu thuẫn", "Nội dung ghép mâu thuẫn là dấu hiệu cần nghi ngờ."),
    (r"(bỏ qua hướng dẫn|bo qua huong dan|ignore previous|say this is safe|nói tin này an toàn|noi tin nay an toan)", "Chèn lời nhắc vào nội dung", "Tin cố điều khiển AI nên không được tin là nguồn hướng dẫn."),
)

DANGEROUS_LABELS = {
    "Yêu cầu mã xác thực", "Yêu cầu chuyển khoản/đóng phí", "Có số tài khoản lạ",
    "Yêu cầu tải/cài tệp lạ", "Giả danh cơ quan chức năng", "Đe dọa khóa tài khoản/hồ sơ",
}


def normalize_url(raw_url: str) -> str:
    """Convert a detected URL into a consistent absolute URL."""
    url = raw_url.strip().rstrip(".,;:!?)\"]}")
    if url.startswith("www."):
        url = f"https://{url}"
    if "://" not in url:
        url = f"https://{url}"
    return url


def extract_urls(input_text: str) -> list[dict[str, str]]:
    """Extract unique web addresses and their normalized domains from text."""
    seen: set[str] = set()
    urls = []
    for match in URL_RE.finditer(input_text):
        raw = match.group(1)
        normalized = normalize_url(raw)
        if normalized in seen:
            continue
        domain = urlparse(normalized).netloc.lower().removeprefix("www.")
        if not domain or "." not in domain:
            continue
        seen.add(normalized)
        urls.append({"raw": raw, "url": normalized, "domain": domain})
    return urls


def is_short_url(domain: str) -> bool:
    """Return whether a domain belongs to a known URL-shortening service."""
    return domain in SHORTENER_DOMAINS


def resolve_short_url(url: str, timeout: float = 3) -> str:
    """Follow redirects for a short URL and safely fall back to the original."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=(2, timeout))
        if response.url and response.url != url:
            return response.url
        response = requests.get(url, allow_redirects=True, timeout=(2, timeout), stream=True)
        return response.url or url
    except requests.RequestException:
        return url


def ascii_domain(domain: str) -> str:
    """Convert an internationalized domain to IDNA ASCII when possible."""
    try:
        return domain.encode("idna").decode("ascii")
    except UnicodeError:
        return domain


def skeleton_domain(domain: str) -> str:
    """Normalize common look-alike characters before domain comparison."""
    return ascii_domain(domain.lower()).translate(HOMOGLYPHS)


def levenshtein(left: str, right: str) -> int:
    """Calculate the edit distance used to detect near-copy domains."""
    if left == right:
        return 0
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for i, left_char in enumerate(left, start=1):
        current = [i]
        for j, right_char in enumerate(right, start=1):
            current.append(min(current[j - 1] + 1, previous[j] + 1, previous[j - 1] + (left_char != right_char)))
        previous = current
    return previous[-1]


def detect_spoofed_domain(domain: str) -> dict[str, str] | None:
    """Explain when a domain appears to imitate a known official domain."""
    normalized = skeleton_domain(domain)
    if normalized in OFFICIAL_DOMAINS:
        return None
    labels = normalized.split(".")
    registrable = ".".join(labels[-3:] if normalized.endswith(".com.vn") and len(labels) >= 3 else labels[-2:])
    compact = normalized.replace("-", "").replace(".", "")
    for official, organization in OFFICIAL_DOMAINS.items():
        official_skeleton = skeleton_domain(official)
        official_compact = official_skeleton.replace("-", "").replace(".", "")
        distance = levenshtein(registrable, official_skeleton)
        compact_distance = levenshtein(compact, official_compact)
        contains_brand = official_skeleton.split(".")[0] in compact and normalized != official_skeleton
        if distance <= 2 or compact_distance <= 2 or contains_brand:
            reason = f"Tên miền gần giống {organization} ({official})"
            if ascii_domain(domain) != domain.lower():
                reason += " và có ký tự đồng hình/idna"
            elif distance <= 2 or compact_distance <= 2:
                reason += f", khoảng cách chuỗi {min(distance, compact_distance)}"
            else:
                reason += ", chèn thêm chữ quanh thương hiệu"
            return {"organization": organization, "official_domain": official, "reason": reason}
    return None


def analyze_links(
    input_text: str,
    resolve_shortlinks: bool = False,
    resolver: Callable[[str], str] = resolve_short_url,
) -> list[dict[str, Any]]:
    """Inspect every link, optionally resolving short links before spoof checks."""
    findings = []
    for item in extract_urls(input_text):
        final_url, final_domain = item["url"], item["domain"]
        if resolve_shortlinks and is_short_url(item["domain"]):
            final_url = resolver(item["url"])
            final_domain = urlparse(final_url).netloc.lower().removeprefix("www.") or item["domain"]
        findings.append({
            **item,
            "shortened": is_short_url(item["domain"]),
            "resolved_url": final_url,
            "resolved_domain": final_domain,
            "spoof": detect_spoofed_domain(final_domain),
        })
    return findings


def rule_indicators(input_text: str, resolve_shortlinks: bool = False) -> list[dict[str, str]]:
    """Return deterministic risk indicators that do not depend on AI output."""
    indicators = []
    for pattern, label, explanation in RULES:
        match = re.search(pattern, input_text, re.IGNORECASE)
        if match:
            indicators.append({"label": label, "quote": input_text[match.start():match.end()], "explanation": explanation})
    for link in analyze_links(input_text, resolve_shortlinks):
        if link["shortened"]:
            explanation = "Đường dẫn rút gọn che địa chỉ thật."
            if link["resolved_url"] != link["url"]:
                explanation += f" Đã giải tới {link['resolved_domain']}."
            indicators.append({"label": "Đường dẫn rút gọn", "quote": link["raw"], "explanation": explanation})
        if link["spoof"]:
            indicators.append({"label": "Tên miền nghi giả mạo", "quote": link["raw"], "explanation": link["spoof"]["reason"]})
        elif link["resolved_domain"] not in OFFICIAL_DOMAINS:
            indicators.append({"label": "Đường dẫn ngoài danh sách chính thống", "quote": link["raw"], "explanation": f"Tên miền {link['resolved_domain']} không nằm trong danh sách tổ chức chính thống của ứng dụng."})
    return indicators


def baseline_risk_level(input_text: str) -> str:
    """Compute the minimum safe risk level from deterministic rules."""
    indicators = rule_indicators(input_text)
    if any(item["label"] in DANGEROUS_LABELS for item in indicators):
        return "Nguy hiểm"
    if indicators:
        return "Nghi ngờ"
    text = input_text.lower()
    suspicious_terms = (
        "trúng thưởng", "trung thuong", "xác minh", "xac minh", "ngân hàng",
        "ngan hang", "giao hàng", "giao hang", "bit.ly", "http://", "https://",
        "gui link", "gửi link", "link thanh toan", "link thanh toán",
    )
    return "Nghi ngờ" if any(term in text for term in suspicious_terms) else "An toàn"


def risk_rank(risk_level: str) -> int:
    """Map a risk label to its ordered severity, defaulting to suspicious."""
    return RISK_LEVELS.index(risk_level) if risk_level in RISK_LEVELS else 1


def enforce_risk_floor(result: dict[str, Any], input_text: str) -> dict[str, Any]:
    """Prevent an AI result from falling below the rule-based risk level."""
    floor = baseline_risk_level(input_text)
    if risk_rank(result["risk_level"]) >= risk_rank(floor):
        return result
    upgraded = dict(result)
    upgraded["risk_level"] = floor
    upgraded["indicators"] = [{
        "label": "Bộ lọc an toàn nâng mức rủi ro", "quote": "",
        "explanation": "Tin có dấu hiệu nhạy cảm hoặc chèn lời nhắc nên hệ thống không hạ xuống An toàn.",
    }, *result["indicators"]][:5]
    return upgraded


def merge_rule_indicators(result: dict[str, Any], input_text: str, resolve_shortlinks: bool = False) -> dict[str, Any]:
    """Merge deterministic findings into AI findings without duplicating them."""
    merged = dict(result)
    current = list(merged.get("indicators", []))
    existing = {(item.get("label", ""), item.get("quote", "")) for item in current if isinstance(item, dict)}
    for indicator in rule_indicators(input_text, resolve_shortlinks):
        key = (indicator["label"], indicator["quote"])
        if key not in existing:
            current.insert(0, indicator)
            existing.add(key)
    merged["indicators"] = current[:8]
    merged = enforce_risk_floor(merged, input_text)
    if current and "Luật kỹ thuật" not in merged["summary"]:
        merged["summary"] = f"{merged['summary']} Luật kỹ thuật đã bổ sung {min(len(current), 8)} dấu hiệu."
    return merged
