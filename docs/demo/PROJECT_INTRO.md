# ScamCheck Demo Introduction

## Product

ScamCheck helps older users and families check suspicious messages before clicking, sending OTP, transferring money, or installing unknown apps.

The app has three AI roles:

- **Thám tử**: analyzes risk, evidence, and recommended actions.
- **Cô tâm lý**: explains the psychological trick in a calm, familiar voice.
- **Người ứng cứu**: gives numbered emergency steps based on what the user already did.

ScamCheck also has a non-AI safety layer: URL extraction, short-link checks, fake-domain detection, rule-based scam signals, result caching, crisis hotline filtering, practice mode, high contrast mode, and shareable summary cards.

Legal notice: ScamCheck only supports reference checking and does not replace legal, financial, medical, or official authority advice.

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python app.py
```

Open:

```text
http://127.0.0.1:5000/
```

For real Gemini calls, fill `.env`:

```text
GEMINI_API_KEY=your_real_key
GEMINI_MODEL=gemini-2.5-flash
FLASK_SECRET_KEY=replace_with_a_random_secret
PUBLIC_PRODUCT_URL=https://your-public-url
```

## Completed Features

- Structured Gemini result for risk level, indicators, quotes, and actions.
- Defensive parser for malformed AI output.
- Session call limit, timeout, retry, AI call log.
- Risk colors and quote highlighting.
- Local history, delete controls, and duplicate-result cache.
- Voice input fallback.
- Cô tâm lý sequential flow for suspicious/dangerous results.
- Prompt-injection guard and risk floor.
- URL extraction, short-link handling, homograph and edit-distance fake-domain detection.
- Rule-based indicators outside AI.
- 60-message evaluation set and confusion matrix.
- Scam library with 12 common scam types.
- 10-question practice mode.
- Verified hotline table and crisis responder flow.
- Phone-number hallucination blocking.
- Share-card PNG with QR code.
- High contrast and larger text modes.

## Team Information

Project: **ScamCheck__**

Team: student FCT hackathon team.

Roles to fill before demo:

- Product/demo lead:
- Backend/AI lead:
- Frontend/UX lead:
- Testing/research lead:
