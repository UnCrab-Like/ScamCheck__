import asyncio
import base64
import hashlib
import json
import os
import queue
import threading
import time
import urllib.error
from datetime import datetime, timezone
from typing import Any

import requests
import httpx
from flask import Flask, jsonify, render_template, request, send_file, session, stream_with_context

from scamcheck.analysis import (
    RISK_LEVELS,
    analyze_links,
    baseline_risk_level,
    detect_spoofed_domain,
    enforce_risk_floor,
    extract_urls,
    merge_rule_indicators,
    risk_rank,
    rule_indicators,
)
from scamcheck.benchmark import run_offline_benchmark
from scamcheck.config import (
    AI_TIMEOUT_SECONDS,
    DEFAULT_RESULT,
    GEMINI_API_URL,
    GEMINI_STREAM_URL,
    MAX_AI_CALLS_PER_SESSION,
    MAX_INPUT_CHARS,
    PSYCHOLOGY_CHAT_SCHEMA,
    PSYCHOLOGY_SCHEMA,
    REQUEST_BUDGET_SECONDS,
    RESCUE_OPTIONS,
    RESPONDER_SCHEMA,
    RESULT_CACHE_LIMIT,
    RESULT_SCHEMA,
    load_local_env,
)
from scamcheck.hotlines import (
    fallback_rescue_steps,
    hotline_contacts,
    sanitize_phone_hallucinations,
    sanitize_responder_steps,
)
from scamcheck.parsing import (
    parse_gemini_result,
    parse_psychology_chat_result,
    parse_psychology_result,
    parse_responder_result as _parse_responder_result,
)
from scamcheck.prompts import (
    build_prompt,
    build_psychology_chat_prompt,
    build_psychology_prompt,
    build_responder_prompt,
)
from scamcheck.share_card import product_url, render_share_card

app = Flask(__name__, template_folder="src/templates", static_folder="static")
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev-only-change-me")


def get_session_state() -> dict[str, Any]:
    """Initialize and expose the current session's AI resource usage."""
    session.setdefault("ai_calls_used", 0)
    session.setdefault("ai_call_log", [])
    session.setdefault("result_cache", {})
    return {
        "used": session["ai_calls_used"],
        "limit": MAX_AI_CALLS_PER_SESSION,
        "logs": session["ai_call_log"],
        "timeout_seconds": AI_TIMEOUT_SECONDS,
        "cache_size": len(session["result_cache"]),
    }


def parse_responder_result(raw: Any) -> dict[str, Any]:
    """Parse responder output while enforcing the verified phone allow-list."""
    return _parse_responder_result(raw, sanitize_responder_steps)


def validate_input(input_text: str) -> str | None:
    """Return a friendly validation error, or None for acceptable input."""
    if not input_text:
        return "Vui lòng nhập nội dung tin nhắn cần kiểm tra."
    if len(input_text) < 8:
        return "Nội dung quá ngắn để đánh giá đáng tin cậy. Hãy nhập nguyên văn tin nhắn."
    if len(input_text) > MAX_INPUT_CHARS:
        return f"Tin nhắn quá dài. Vui lòng rút gọn dưới {MAX_INPUT_CHARS} ký tự."
    if sum(1 for ch in input_text if ord(ch) < 32 and ch not in "\n\t\r") > 0:
        return "Tin nhắn có ký tự không hỗ trợ. Vui lòng dán lại nội dung dạng văn bản thường."
    if len(set(input_text.replace(" ", ""))) <= 2 and len(input_text) > 30:
        return "Nội dung lặp bất thường, chưa đủ thông tin để kiểm tra."
    return None


def cache_key(input_text: str) -> str:
    """Create a stable, privacy-preserving key for duplicate-message caching."""
    return hashlib.sha256(input_text.strip().lower().encode("utf-8")).hexdigest()


def get_cached_result(input_text: str) -> dict[str, Any] | None:
    """Return a cached analysis without consuming another Gemini call."""
    cache = session.get("result_cache", {})
    item = cache.get(cache_key(input_text))
    if not item:
        return None
    item = dict(item)
    item["from_cache"] = True
    return item


def set_cached_result(input_text: str, result: dict[str, Any]) -> None:
    """Store an analysis and evict the oldest entries above the cache limit."""
    cache = dict(session.get("result_cache", {}))
    key = cache_key(input_text)
    cache[key] = {**result, "cached_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if len(cache) > RESULT_CACHE_LIMIT:
        oldest = sorted(cache.items(), key=lambda pair: pair[1].get("cached_at", ""))[: len(cache) - RESULT_CACHE_LIMIT]
        for old_key, _ in oldest:
            cache.pop(old_key, None)
    session["result_cache"] = cache
    session.modified = True


def extract_candidate_text(payload: dict[str, Any]) -> str:
    """Extract text from Gemini's candidate envelope or raise a clear error."""
    candidates = payload.get("candidates", [])
    if not candidates:
        raise ValueError("Gemini không trả kết quả.")
    parts = candidates[0].get("content", {}).get("parts", [])
    if not parts or "text" not in parts[0]:
        raise ValueError("Gemini trả dữ liệu thiếu phần text.")
    return parts[0]["text"]


async def call_gemini_json(
    prompt: str,
    schema: dict[str, Any],
    parser,
    deadline: float,
    max_retries: int = 2,
    on_chunk=None,
    sleep_func=None,
) -> dict[str, Any]:
    """Call Gemini with structured output, timeout budgeting, and bounded retries."""
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Thiếu GEMINI_API_KEY trên máy chủ.")

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    last_error: Exception | None = None
    # Retries share one deadline so exponential backoff cannot exceed the
    # request-level response budget.
    for attempt in range(max_retries + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("Hết ngân sách thời gian gọi AI.")
        attempt_timeout = min(AI_TIMEOUT_SECONDS, remaining)
        try:
            if on_chunk:
                return await post_json_stream_async(
                    GEMINI_STREAM_URL, body, headers, parser, attempt_timeout, on_chunk
                )
            return await post_json_async(GEMINI_API_URL, body, headers, parser, attempt_timeout)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code not in (429, 500, 502, 503, 504) or attempt == max_retries:
                raise
            delay = 2**attempt
            if time.monotonic() + delay >= deadline:
                raise TimeoutError("Không đủ thời gian để thử lại Gemini.")
            await (sleep_func or asyncio.sleep)(delay)
        except (requests.RequestException, httpx.HTTPError, TimeoutError, asyncio.TimeoutError) as exc:
            last_error = exc
            if attempt == max_retries:
                raise
            delay = 2**attempt
            if time.monotonic() + delay >= deadline:
                raise TimeoutError("Không đủ thời gian để thử lại Gemini.")
            await (sleep_func or asyncio.sleep)(delay)
    raise RuntimeError(f"Không gọi được Gemini: {last_error}")


def post_json(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    parser,
    timeout: float,
) -> dict[str, Any]:
    """Send one blocking JSON request and parse its Gemini response."""
    request_body = json.dumps(body).encode("utf-8")
    response = requests.post(url, data=request_body, headers=headers, timeout=(3, timeout))
    if response.status_code >= 400:
        raise urllib.error.HTTPError(url, response.status_code, response.text, response.headers, None)
    payload = response.json()
    return parser(extract_candidate_text(payload))


async def post_json_async(url, body, headers, parser, timeout):
    """Send an asynchronous JSON request and parse its Gemini response."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=3)) as client:
        response = await client.post(url, json=body, headers=headers)
    if response.status_code >= 400:
        raise urllib.error.HTTPError(url, response.status_code, response.text, response.headers, None)
    return parser(extract_candidate_text(response.json()))


async def post_json_stream_async(url, body, headers, parser, timeout, on_chunk):
    """Stream Gemini SSE chunks without blocking the event loop."""
    chunks: list[str] = []
    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=3)) as client:
        async with client.stream("POST", url, json=body, headers=headers) as response:
            if response.status_code >= 400:
                error_text = (await response.aread()).decode("utf-8", errors="replace")
                raise urllib.error.HTTPError(url, response.status_code, error_text, response.headers, None)
            async for raw_line in response.aiter_lines():
                if not raw_line or not raw_line.startswith("data:"):
                    continue
                payload = json.loads(raw_line[5:].strip())
                chunk = extract_candidate_text(payload)
                if chunk:
                    chunks.append(chunk)
                    on_chunk(chunk)
    return parser("".join(chunks))


def post_json_stream(
    url: str,
    body: dict[str, Any],
    headers: dict[str, str],
    parser,
    timeout: float,
    on_chunk,
) -> dict[str, Any]:
    """Consume Gemini SSE chunks while assembling one final structured result."""
    response = requests.post(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=headers,
        timeout=(3, timeout),
        stream=True,
    )
    if response.status_code >= 400:
        raise urllib.error.HTTPError(url, response.status_code, response.text, response.headers, None)

    chunks: list[str] = []
    for raw_line in response.iter_lines(decode_unicode=True):
        if not raw_line or not raw_line.startswith("data:"):
            continue
        payload = json.loads(raw_line[5:].strip())
        chunk = extract_candidate_text(payload)
        if chunk:
            chunks.append(chunk)
            on_chunk(chunk)
    return parser("".join(chunks))


def gemini_error_message(exc: urllib.error.HTTPError) -> str:
    """Translate Gemini HTTP failures into user-friendly Vietnamese messages."""
    reason = str(getattr(exc, "reason", "") or "")
    if exc.code in (400, 401, 403) and (
        "API_KEY_INVALID" in reason or "API key not valid" in reason
    ):
        return "Khóa Gemini trên máy chủ không hợp lệ. Vui lòng cập nhật GEMINI_API_KEY trong .env."
    if exc.code == 429:
        return "Gemini đang giới hạn tần suất. Ứng dụng đã tự thử lại 2 lần nhưng chưa thành công."
    return "Dịch vụ AI đang lỗi tạm thời. Vui lòng thử lại sau."


async def run_ai_sequence(input_text: str, started: float, allow_psychology: bool, on_chunk=None) -> dict[str, Any]:
    """Run Detective first, then Psychologist only for risky results."""
    deadline = started + REQUEST_BUDGET_SECONDS
    detective_options = {"max_retries": 2}
    if on_chunk is not None:
        detective_options["on_chunk"] = on_chunk
    detective = await call_gemini_json(
        build_prompt(input_text),
        RESULT_SCHEMA,
        parse_gemini_result,
        deadline,
        **detective_options,
    )
    detective = merge_rule_indicators(detective, input_text, resolve_shortlinks=True)

    # Psychology is isolated so its failure cannot hide a valid Detective result.
    psychology = None
    psychology_error = None
    if detective["risk_level"] in ("Nghi ngờ", "Nguy hiểm"):
        if not allow_psychology:
            psychology_error = "Phiên này không còn đủ lượt AI để gọi Cô tâm lý. Kết quả Thám tử vẫn dùng được."
        else:
            try:
                psychology = await call_gemini_json(
                    build_psychology_prompt(input_text, detective),
                    PSYCHOLOGY_SCHEMA,
                    parse_psychology_result,
                    deadline,
                    max_retries=0,
                )
            except Exception as exc:
                app.logger.warning("Psychology call failed: %s", exc)
                psychology_error = "Cô tâm lý chưa phản hồi được lúc này, nhưng kết quả Thám tử vẫn dùng được."

    return {
        "detective": detective,
        "psychology": psychology,
        "psychology_error": psychology_error,
    }


async def run_responder(
    input_text: str,
    situation: str,
    detective_result: dict[str, Any],
    started: float,
) -> dict[str, Any]:
    """Generate and sanitize a scenario-specific crisis response plan."""
    contacts = hotline_contacts()
    deadline = started + REQUEST_BUDGET_SECONDS
    try:
        result = await call_gemini_json(
            build_responder_prompt(input_text, situation, detective_result, contacts),
            RESPONDER_SCHEMA,
            parse_responder_result,
            deadline,
            max_retries=0,
        )
        if result["steps"]:
            return {"steps": result["steps"], "source": "ai_sanitized"}
    except Exception as exc:
        app.logger.warning("Responder call failed: %s", exc)
    return {"steps": fallback_rescue_steps(situation), "source": "verified_template"}


async def run_psychology_chat(
    input_text: str,
    detective_result: dict[str, Any],
    history: list[dict[str, str]],
    started: float,
) -> dict[str, str]:
    """Continue the psychologist conversation within the shared time budget."""
    return await call_gemini_json(
        build_psychology_chat_prompt(input_text, detective_result, history),
        PSYCHOLOGY_CHAT_SCHEMA,
        parse_psychology_chat_result,
        started + REQUEST_BUDGET_SECONDS,
        max_retries=0,
    )


def state_machine_metrics(result: dict[str, Any] | None, situation: str | None) -> dict[str, Any]:
    """Describe the orchestration state and calls saved versus a naive flow."""
    risk = ((result or {}).get("detective") or {}).get("risk_level")
    actual = 1
    if risk in ("Nghi ngờ", "Nguy hiểm"):
        actual += 1
    if situation:
        actual += 1
    naive = 3
    return {
        "state": "responder_ready" if situation else "awaiting_situation" if risk in ("Nghi ngờ", "Nguy hiểm") else "done_safe",
        "actual_ai_calls": actual,
        "naive_ai_calls": naive,
        "saved_ai_calls": max(0, naive - actual),
    }


def log_ai_call(input_text: str, role: str, summary: str) -> None:
    """Append bounded, non-secret call metadata to the browser session."""
    log = list(session.get("ai_call_log", []))
    log.append(
        {
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "input_length": len(input_text),
            "role": role,
            "summary": summary,
        }
    )
    session["ai_call_log"] = log[-MAX_AI_CALLS_PER_SESSION:]
    session.modified = True


@app.route("/")
def index():
    """Render the primary message-checking page."""
    return render_template("index.html", active_page="checker")


@app.route("/library")
def library_page():
    """Render the scam-pattern library without a separate template."""
    return render_template("index.html", active_page="library")


@app.route("/practice")
def practice_page():
    """Render the ten-question training mode."""
    return render_template("index.html", active_page="practice")


@app.route("/history")
def history_page():
    """Render locally stored recent analyses."""
    return render_template("index.html", active_page="history")


@app.route("/ai-log")
def ai_log_page():
    """Render the current session's bounded AI call log."""
    return render_template("index.html", active_page="log")


@app.route("/accessibility")
def accessibility_page():
    """Render the accessibility self-check page."""
    return render_template("index.html", active_page="accessibility")


@app.route("/settings")
def settings_page():
    """Render persistent display and accessibility settings."""
    return render_template("index.html", active_page="settings")


@app.route("/health")
def health():
    """Provide a lightweight health check for the hosting platform."""
    return jsonify({"status": "ok"})


@app.route("/session_state")
def session_state():
    """Expose resource usage and call logs for the current browser session."""
    return jsonify(get_session_state())


@app.route("/offline_benchmark", methods=["POST"])
def offline_benchmark():
    """Run the categorized rule benchmark without spending any AI calls."""
    before = get_session_state()["used"]
    result = run_offline_benchmark()
    result["session_ai_calls_before"] = before
    result["session_ai_calls_after"] = get_session_state()["used"]
    result["session_ai_limit"] = MAX_AI_CALLS_PER_SESSION
    return jsonify(result)


@app.route("/transcribe", methods=["POST"])
def transcribe():
    """Transcribe a bounded audio upload while enforcing the session call cap."""
    state = get_session_state()
    if state["used"] >= MAX_AI_CALLS_PER_SESSION:
        return jsonify({"error": "Phiên này đã dùng hết lượt AI."}), 429
    audio = request.files.get("audio")
    if not audio:
        return jsonify({"error": "Không nhận được bản ghi âm."}), 400
    audio_bytes = audio.read(5 * 1024 * 1024 + 1)
    if not audio_bytes or len(audio_bytes) > 5 * 1024 * 1024:
        return jsonify({"error": "Bản ghi phải nhỏ hơn 5 MB."}), 400
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return jsonify({"error": "Máy chủ chưa cấu hình Gemini."}), 503

    mime_type = audio.mimetype if audio.mimetype.startswith("audio/") else "audio/webm"
    body = {
        "contents": [{"parts": [
            {"text": "Chép lại nguyên văn lời nói tiếng Việt trong tệp âm thanh. Chỉ trả phần văn bản, không bình luận."},
            {"inlineData": {"mimeType": mime_type, "data": base64.b64encode(audio_bytes).decode("ascii")}},
        ]}],
        "generationConfig": {"temperature": 0},
    }
    try:
        response = requests.post(
            GEMINI_API_URL,
            json=body,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            timeout=(3, AI_TIMEOUT_SECONDS),
        )
        response.raise_for_status()
        transcript = extract_candidate_text(response.json()).strip()
    except (requests.RequestException, ValueError, KeyError) as exc:
        app.logger.warning("Audio transcription failed: %s", exc)
        return jsonify({"error": "Chưa chuyển được giọng nói thành chữ. Vui lòng thử lại."}), 503

    session["ai_calls_used"] = int(session.get("ai_calls_used", 0)) + 1
    log_ai_call(transcript, "Nhập giọng nói", "Đã chuyển bản ghi âm thành văn bản.")
    return jsonify({"transcript": transcript, "session": get_session_state()})


@app.route("/scam_check", methods=["POST"])
def scam_check():
    """Validate, cache, analyze, log, and return one complete scam check."""
    started = time.monotonic()
    payload = request.get_json(silent=True) or {}
    input_text = str(payload.get("input_text", "")).strip()

    message = validate_input(input_text)
    if message:
        return jsonify({"error": message, "session": get_session_state()}), 400

    state = get_session_state()
    cached = get_cached_result(input_text)
    if cached:
        return jsonify({"result": cached["result"], "session": state, "elapsed_seconds": 0, "from_cache": True})

    if state["used"] >= MAX_AI_CALLS_PER_SESSION:
        return (
            jsonify(
                {
                    "error": "Phiên này đã dùng hết lượt kiểm tra AI. Hãy xem lại lịch sử hoặc mở phiên mới sau.",
                    "session": state,
                }
            ),
            429,
        )

    try:
        available_calls = MAX_AI_CALLS_PER_SESSION - int(session.get("ai_calls_used", 0))
        result = asyncio.run(run_ai_sequence(input_text, started, available_calls >= 2))
        calls_used = 1
        if result["detective"]["risk_level"] in ("Nghi ngờ", "Nguy hiểm") and available_calls >= 2:
            calls_used = 2
        session["ai_calls_used"] = int(session.get("ai_calls_used", 0)) + calls_used
        detective = result["detective"]
        log_ai_call(input_text, "Thám tử", f"{detective['risk_level']}: {detective['summary']}")
        if result.get("psychology"):
            log_ai_call(input_text, "Cô tâm lý", result["psychology"]["explanation"])
        response = {
            "result": result,
            "session": get_session_state(),
            "elapsed_seconds": round(time.monotonic() - started, 2),
            "from_cache": False,
            "flow": state_machine_metrics(result, None),
        }
        set_cached_result(input_text, {"result": result})
        return jsonify(response)
    except urllib.error.HTTPError as exc:
        error = gemini_error_message(exc)
        return jsonify({"error": error, "session": get_session_state()}), 503
    except (RuntimeError, requests.RequestException, httpx.HTTPError, TimeoutError, asyncio.TimeoutError) as exc:
        app.logger.warning("AI call failed: %s", exc)
        return (
            jsonify(
                {
                    "error": "Chưa thể kiểm tra bằng AI lúc này. Vui lòng kiểm tra khóa Gemini hoặc kết nối mạng.",
                    "session": get_session_state(),
                }
            ),
            503,
        )


@app.route("/scam_check_stream", methods=["POST"])
def scam_check_stream():
    """Stream Detective output as SSE events from a background worker."""
    started = time.monotonic()
    payload = request.get_json(silent=True) or {}
    input_text = str(payload.get("input_text", "")).strip()
    message = validate_input(input_text)
    if message:
        return jsonify({"error": message, "session": get_session_state()}), 400

    cached = get_cached_result(input_text)
    if cached:
        def cached_events():
            """Return a cached result using the same SSE contract as a live call."""
            yield f"event: result\ndata: {json.dumps({'result': cached['result'], 'from_cache': True}, ensure_ascii=False)}\n\n"
        return app.response_class(stream_with_context(cached_events()), mimetype="text/event-stream")

    state = get_session_state()
    if state["used"] >= MAX_AI_CALLS_PER_SESSION:
        return jsonify({"error": "Phiên này đã dùng hết lượt kiểm tra AI.", "session": state}), 429

    available_calls = MAX_AI_CALLS_PER_SESSION - int(session.get("ai_calls_used", 0))
    allow_psychology = available_calls >= 2
    session["ai_calls_used"] = int(session.get("ai_calls_used", 0)) + 1
    log_ai_call(input_text, "Thám tử", "Đang nhận phản hồi theo dòng từ Gemini.")

    events: queue.Queue[tuple[str, Any]] = queue.Queue()

    def on_chunk(chunk: str) -> None:
        """Forward one Gemini text fragment to the response generator."""
        events.put(("chunk", chunk))

    def run_worker() -> None:
        """Run asynchronous AI orchestration outside Flask's request thread."""
        try:
            result = asyncio.run(run_ai_sequence(input_text, started, allow_psychology, on_chunk=on_chunk))
            events.put(("result", result))
        except Exception as exc:
            app.logger.warning("Streaming AI call failed: %s", exc)
            events.put(("error", "Gemini chưa phản hồi được. Vui lòng thử lại sau."))
        finally:
            events.put(("done", None))

    threading.Thread(target=run_worker, daemon=True).start()

    @stream_with_context
    def generate():
        """Yield queued worker events using the Server-Sent Events format."""
        yield "event: status\ndata: {\"message\": \"Đã kết nối luồng Gemini\"}\n\n"
        while True:
            event, value = events.get()
            if event == "done":
                break
            if event == "chunk":
                data = {"text": value}
            elif event == "result":
                data = {"result": value, "from_cache": False}
            else:
                data = {"message": value}
            yield f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

    response = app.response_class(generate(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@app.route("/stream_finalize", methods=["POST"])
def stream_finalize():
    """Validate and persist the final structured result from a streamed check."""
    payload = request.get_json(silent=True) or {}
    input_text = str(payload.get("input_text", "")).strip()
    raw_result = payload.get("result") or {}
    if validate_input(input_text):
        return jsonify({"error": "Nội dung hoàn tất luồng không hợp lệ."}), 400
    if get_cached_result(input_text):
        return jsonify({"session": get_session_state(), "cached": True})

    detective = parse_gemini_result(raw_result.get("detective"))
    psychology = raw_result.get("psychology")
    result = {
        "detective": detective,
        "psychology": parse_psychology_result(psychology) if psychology else None,
        "psychology_error": str(raw_result.get("psychology_error") or "") or None,
    }
    logs = list(session.get("ai_call_log", []))
    for item in reversed(logs):
        if item.get("role") == "Thám tử" and item.get("summary") == "Đang nhận phản hồi theo dòng từ Gemini.":
            item["summary"] = f"{detective['risk_level']}: {detective['summary']}"
            break
    session["ai_call_log"] = logs
    session.modified = True
    if result["psychology"] and int(session.get("ai_calls_used", 0)) < MAX_AI_CALLS_PER_SESSION:
        session["ai_calls_used"] = int(session.get("ai_calls_used", 0)) + 1
        log_ai_call(input_text, "Cô tâm lý", result["psychology"]["explanation"])
    set_cached_result(input_text, {"result": result})
    return jsonify({"session": get_session_state(), "cached": False})


@app.route("/psychology_chat", methods=["POST"])
def psychology_chat():
    """Handle a bounded follow-up conversation with the Psychologist role."""
    started = time.monotonic()
    payload = request.get_json(silent=True) or {}
    input_text = str(payload.get("input_text", "")).strip()[:MAX_INPUT_CHARS]
    detective = payload.get("detective") if isinstance(payload.get("detective"), dict) else DEFAULT_RESULT
    raw_history = payload.get("history") if isinstance(payload.get("history"), list) else []
    history = []
    for item in raw_history[-8:]:
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
            continue
        content = str(item.get("content", "")).strip()[:1500]
        if content:
            history.append({"role": item["role"], "content": content})

    if not input_text or not history or history[-1]["role"] != "user":
        return jsonify({"error": "Bác hãy kể thêm chuyện đã xảy ra để cô hỗ trợ."}), 400
    if int(session.get("ai_calls_used", 0)) >= MAX_AI_CALLS_PER_SESSION:
        return jsonify({"error": "Phiên này đã hết lượt AI. Bác vẫn có thể dùng các bước ứng cứu có sẵn."}), 429

    session["ai_calls_used"] = int(session.get("ai_calls_used", 0)) + 1
    session.modified = True
    try:
        result = asyncio.run(run_psychology_chat(input_text, detective, history, started))
    except Exception as exc:
        app.logger.warning("Psychology chat failed: %s", exc)
        return jsonify({"error": "Cô chưa phản hồi được lúc này. Bác hãy ưu tiên các bước ứng cứu bên dưới."}), 502
    log_ai_call(history[-1]["content"], "Cô tâm lý", result["reply"])
    return jsonify({"reply": result["reply"], "session": get_session_state()})


@app.route("/rescue_plan", methods=["POST"])
def rescue_plan():
    """Return a sanitized crisis plan for one of the four supported situations."""
    started = time.monotonic()
    payload = request.get_json(silent=True) or {}
    input_text = str(payload.get("input_text", "")).strip()
    situation = str(payload.get("situation", "")).strip()
    detective = payload.get("detective") or DEFAULT_RESULT

    if situation not in RESCUE_OPTIONS:
        return jsonify({"error": "Vui lòng chọn một tình huống ứng cứu hợp lệ."}), 400
    if not input_text:
        return jsonify({"error": "Thiếu nội dung tin nhắn để lập kịch bản ứng cứu."}), 400

    result = asyncio.run(run_responder(input_text, situation, detective, started))
    return jsonify(
        {
            "responder": result,
            "situation": situation,
            "flow": state_machine_metrics({"detective": detective}, situation),
            "elapsed_seconds": round(time.monotonic() - started, 2),
        }
    )


@app.route("/share_card", methods=["POST"])
def share_card():
    """Generate a downloadable PNG summary card for a completed analysis."""
    payload = request.get_json(silent=True) or {}
    result = payload.get("result") or {}
    image = render_share_card(result)
    return send_file(image, mimetype="image/png", as_attachment=True, download_name="scamcheck-summary.png")


if __name__ == "__main__":
    app.run(debug=True, port=int(os.getenv("PORT", "5000")))
