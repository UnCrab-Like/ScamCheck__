# ScamCheck__

ScamCheck is a demo Flask app for checking suspicious messages with Gemini. It is a student project and is not affiliated with any public authority, bank, or security service.

## Features

- Large message input, sample messages, loading state, and fixed legal footer.
- Gemini structured JSON result: `risk_level`, `indicators`, `actions`, `summary`.
- Risk badge colors: `An toàn` green, `Nghi ngờ` yellow, `Nguy hiểm` red.
- Quote highlighting in the original message when Gemini returns matching excerpts.
- 10-item browser history saved in `localStorage`; opening history does not call Gemini again.
- Per-session AI limit: 20 calls, 30-second timeout per call, retry with exponential backoff for rate limits and temporary server errors.
- In-session AI call log with time, input length, and result summary.
- Defensive parser and edge-case tests so malformed AI output does not break the app.
- Voice input button using browser speech recognition when available; on iPhone Safari, users can use the keyboard microphone fallback.
- Sequential AI flow: Detective first, then "Cô tâm lý" only for `Nghi ngờ` or `Nguy hiểm`.
- Prompt-injection hardening: untrusted message delimiters in prompts plus a backend risk floor for OTP, money transfer, malware files, fake authority, and instruction-injection wording.
- Scam library with 12 common scam types and client-side filters for `Giả ngân hàng`, `Giả công an`, `Trúng thưởng`, and `Giả giao hàng`.
- Technical URL checks: regex extraction, short-link expansion, spoofed-domain detection with homograph normalization and Levenshtein distance.
- Rule-based detector for OTP, money transfer, unknown account numbers, urgency, malware-like files, fake authorities, prompt injection, and suspicious domains.
- Duplicate-result cache in the browser and server session so repeated messages do not spend another AI call.
- 10-question practice mode with per-question feedback and final score.
- Verified responder hotline table in `data/hotlines_verified.json`; responder output is not allowed to show phone numbers outside that table.
- Four-scenario rescue flow after risky results: clicked link, shared info/OTP, sent money, installed suspicious app.
- Server-generated PNG share card with risk level, main indicator, ScamCheck name, and QR code to `PUBLIC_PRODUCT_URL`.
- High-contrast mode and larger text mode are saved in the browser for later visits.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Fill `.env` with your real values:

```bash
GEMINI_API_KEY=your_real_key
GEMINI_MODEL=gemini-3.5-flash
FLASK_SECRET_KEY=replace_with_a_random_secret
PORT=5000
PUBLIC_PRODUCT_URL=https://your-public-scamcheck-url.example
```

Do not commit `.env`. `.gitignore` excludes real environment files and keeps `.env.example` as the teammate template.

## Run

```bash
source .venv/bin/activate
python app.py
```

Open `http://127.0.0.1:5000/`.

## Test

```bash
source .venv/bin/activate
pytest
```

The tests cover malformed Gemini output and 12 input edge cases, including fake malicious links and contradictory title/body content.

## Regression Check

Run the labeled 20-message regression set:

```bash
source .venv/bin/activate
python scripts/run_regression.py
```

The command prints a table with expected labels, predicted labels, and `OK` or `MISS` for each case. It uses the same backend risk-floor logic that protects the Gemini result from obvious prompt-injection downgrades.

## Quality Evaluation

Run the 60-message labeled evaluation set and confusion matrix:

```bash
source .venv/bin/activate
python scripts/evaluate_quality.py
```

Data files:

- `data/evaluation_60.json`: 60 labeled messages, balanced across `An toàn`, `Nghi ngờ`, and `Nguy hiểm`, each with a label reason.
- `data/evaluation_hard_15.json`: 15 ambiguous hard cases for manual review.

The report prints before/after accuracy, coverage, a confusion matrix, and at least three concrete weaknesses.

To collect evidence from the real Gemini model, including schema reliability, latency, accuracy, and dangerous downgrades:

```bash
python scripts/evaluate_live_gemini.py --limit 10
# Full labeled evaluation (uses 60 Gemini calls):
python scripts/evaluate_live_gemini.py --limit 60
```

This command requires `GEMINI_API_KEY` and intentionally never prints the key.

## Responder Operations

Responder safety documentation is in `docs/operations_safety.md`.

Important files:

- `data/hotlines_verified.json`: verified official phone numbers and sources.
- `docs/operations_safety.md`: state machine, operating checklist, safety self-assessment.

The responder flow never trusts AI-generated phone numbers. Backend output is filtered through the verified hotline table before display.

## Public Deployment

This Flask app needs a Python server for secure Gemini calls. GitHub Pages can publish only static files, so do not place `GEMINI_API_KEY` in frontend JavaScript or a Pages-only build.

For a public demo, deploy the Flask app to a Python host such as Render, Railway, Fly.io, or a school server, then set these environment variables in the hosting dashboard:

- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `FLASK_SECRET_KEY`
- `PORT`

If the mentor specifically requires GitHub Pages from the main branch, publish only a static landing/proxy page there and keep Gemini calls on a backend service. In GitHub: Settings -> Pages -> Build and deployment -> Deploy from branch -> `main`.

### Render deployment for phone and desktop

The included `render.yaml` runs the Flask backend with Gunicorn and exposes `/health` for hosting checks.

1. Push the clean `main` branch to GitHub.
2. In Render, choose **New → Blueprint** and select this repository.
3. Enter `GEMINI_API_KEY` and the final public address as `PUBLIC_PRODUCT_URL`.
4. Deploy, then open the HTTPS address on iPhone Safari and a desktop browser.
5. Allow microphone access when testing voice input. Safari uses recorded audio transcription when browser speech recognition is unavailable.

Do not use a Pages-only deployment for the checker: it would either expose the Gemini key or omit the Python safety layer.

## Legal Notice

The app displays this fixed footer on every screen:

`ScamCheck chỉ hỗ trợ tham khảo, không thay thế tư vấn pháp lý, tài chính hoặc quyết định của cơ quan chức năng.`
