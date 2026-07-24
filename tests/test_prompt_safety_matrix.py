"""Broad offline regression coverage for messages submitted to ScamCheck.

The examples intentionally use reserved domains (``.example`` and
``example.com``) and fictional contact details.  Nothing in this module makes a
network request or calls Gemini, so it is safe and deterministic in CI.
"""

from __future__ import annotations

import re

import pytest

from app import app
from scamcheck.analysis import (
    analyze_links,
    baseline_risk_level,
    detect_spoofed_domain,
    extract_urls,
    rule_indicators,
)
from scamcheck.benchmark import load_offline_benchmark, run_offline_benchmark
from scamcheck.hotlines import (
    allowed_phone_numbers,
    fallback_rescue_steps,
    hotline_contacts,
    normalize_phone,
    sanitize_phone_hallucinations,
)


BENCHMARK_CASES = load_offline_benchmark()["cases"]
PROMPT_CASES = [
    pytest.param(
        case["text"],
        case["expected_risk"],
        case["category"],
        id=case["id"],
    )
    for case in BENCHMARK_CASES
]


@pytest.mark.parametrize(("text", "expected_risk", "category"), PROMPT_CASES)
def test_prompt_matrix_has_expected_deterministic_risk_floor(text, expected_risk, category):
    assert category
    assert baseline_risk_level(text) == expected_risk


@pytest.mark.parametrize(("text", "expected_risk", "category"), PROMPT_CASES)
def test_every_prompt_is_accepted_as_realistic_input(text, expected_risk, category):
    """Keep the corpus useful for route tests: no tiny or oversized samples."""
    del expected_risk, category
    assert 10 <= len(text) <= 5000
    assert not any(ord(char) < 32 and char not in "\n\t" for char in text)


def test_offline_benchmark_returns_score_and_category_breakdown():
    result = run_offline_benchmark()

    assert result["score"] == result["total"] == len(BENCHMARK_CASES)
    assert result["percentage"] == 100
    assert result["ai_calls_used"] == 0
    assert len(result["categories"]) >= 10
    assert all(item["category"] and item["total"] for item in result["categories"])


def test_offline_benchmark_route_does_not_consume_session_ai_calls():
    app.config.update(TESTING=True, SECRET_KEY="offline-benchmark")
    client = app.test_client()
    before = client.get("/session_state").get_json()["used"]
    response = client.post("/offline_benchmark")
    data = response.get_json()
    after = client.get("/session_state").get_json()["used"]

    assert response.status_code == 200
    assert data["score"] == data["total"]
    assert data["ai_calls_used"] == 0
    assert data["session_ai_calls_before"] == data["session_ai_calls_after"]
    assert before == after


@pytest.mark.parametrize(
    ("text", "domains"),
    [
        (
            "Mail admin@example.com; mở https://account-check.example/login?ref=mail.",
            ["account-check.example"],
        ),
        (
            "Hai trang: vietcombank-login.com và https://example.com/help.",
            ["vietcombank-login.com", "example.com"],
        ),
        ("Link rút gọn bit.ly/abc, lặp lại bit.ly/abc.", ["bit.ly"]),
        ("Chỉ có email support@example.org, không có trang web.", []),
    ],
)
def test_url_extraction_handles_websites_without_treating_emails_as_links(text, domains):
    assert [item["domain"] for item in extract_urls(text)] == domains


@pytest.mark.parametrize(
    "domain",
    [
        "vietcombank-login.com",
        "vietcombank-secure.vn",
        "bidv-support.com",
        "techcombank-login.com",
        "mbbank-security.com",
        "momo-voucher.vn",
        "vnpay-refund.top",
        "viettelpost-update.com",
    ],
)
def test_fake_brand_websites_are_identified_as_spoofs(domain):
    finding = detect_spoofed_domain(domain)
    assert finding is not None
    assert finding["official_domain"]
    assert finding["organization"] in finding["reason"]


def test_short_link_can_be_analyzed_with_a_fake_resolver_without_network_access():
    resolved = "https://vietcombank-login.com/otp"
    findings = analyze_links(
        "Đóng phí tại bit.ly/phi-hang",
        resolve_shortlinks=True,
        resolver=lambda url: resolved,
    )

    assert len(findings) == 1
    assert findings[0]["shortened"] is True
    assert findings[0]["resolved_url"] == resolved
    assert findings[0]["resolved_domain"] == "vietcombank-login.com"
    assert findings[0]["spoof"]["organization"] == "Vietcombank"


def test_multi_signal_message_reports_phone_link_payment_and_urgency_context():
    text = (
        "Trong 10 phút hãy chuyển khoản phí hồ sơ, rồi xác minh OTP tại "
        "https://vietcombank-login.com hoặc gọi 0909 111 222."
    )
    labels = {item["label"] for item in rule_indicators(text)}

    assert {
        "Yêu cầu mã xác thực",
        "Yêu cầu chuyển khoản/đóng phí",
        "Tạo áp lực gấp gáp",
        "Tên miền nghi giả mạo",
    } <= labels
    assert baseline_risk_level(text) == "Nguy hiểm"


def test_verified_hotlines_are_unique_complete_and_https_sourced():
    contacts = hotline_contacts()
    ids = [item["id"] for item in contacts]
    normalized_numbers = [normalize_phone(item["phone"]) for item in contacts]

    assert len(contacts) >= 13
    assert len(ids) == len(set(ids))
    assert len(normalized_numbers) == len(set(normalized_numbers))
    assert {"police", "information_security", "bank"} <= {item["type"] for item in contacts}
    assert all(re.fullmatch(r"\d{3,11}", number) for number in normalized_numbers)
    assert all(item["name"] and item["purpose"] for item in contacts)
    assert all(item["source_url"].startswith("https://") for item in contacts)


@pytest.mark.parametrize("contact", hotline_contacts(), ids=lambda item: item["id"])
def test_every_verified_hotline_survives_phone_sanitization(contact):
    rendered = sanitize_phone_hallucinations(
        f"Gọi {contact['name']} theo số {contact['phone']}."
    )
    assert contact["phone"] in rendered
    assert "[số đã bị chặn]" not in rendered


@pytest.mark.parametrize(
    "unknown",
    ["0909111222", "0987 654 321", "+84 909 111 222", "024-9999-8888"],
)
def test_unverified_phone_numbers_are_blocked_in_generated_guidance(unknown):
    cleaned = sanitize_phone_hallucinations(f"Hãy gọi {unknown} để được giúp đỡ.")
    assert unknown not in cleaned
    assert "[số đã bị chặn]" in cleaned


def test_hotline_allowlist_contains_local_and_country_code_bank_variants():
    allowed = allowed_phone_numbers()
    assert "1900545413" in allowed
    assert "113" in allowed
    # Guard the conversion behavior if a future verified contact uses a 0-prefix.
    for contact in hotline_contacts():
        local = normalize_phone(contact["phone"])
        if local.startswith("0"):
            assert f"84{local[1:]}" in allowed


@pytest.mark.parametrize(
    "situation",
    ["clicked_link", "shared_info", "sent_money", "installed_app"],
)
def test_all_rescue_scenarios_only_render_verified_phone_numbers(situation):
    steps = fallback_rescue_steps(situation)
    combined = " ".join(value for step in steps for value in step.values())

    assert len(steps) >= 3
    assert "[số đã bị chặn]" not in combined
    for match in re.finditer(r"(?<!\d)\d{3,11}(?!\d)", combined):
        assert match.group(0) in allowed_phone_numbers()


@pytest.mark.parametrize(
    ("path", "page"),
    [
        ("/", "checker"),
        ("/library", "library"),
        ("/practice", "practice"),
        ("/history", "history"),
        ("/ai-log", "log"),
        ("/accessibility", "accessibility"),
        ("/settings", "settings"),
    ],
)
def test_all_feature_webpages_load_and_identify_the_active_page(path, page):
    app.config.update(TESTING=True, SECRET_KEY="prompt-matrix-pages")
    response = app.test_client().get(path)
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert f'data-page="{page}"' in html
    assert f'href="{path}" aria-current="page"' in html
