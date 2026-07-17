# ScamCheck Operations And Safety

## Hotline Table

Verified contacts are stored in `data/hotlines_verified.json`.

Rules:

- Do not put phone numbers directly into AI prompts outside this file.
- Update `last_verified` whenever checking sources again.
- Keep `source_url` for every number.
- Responder output must pass `sanitize_phone_hallucinations` before display.

## State Machine

```text
input
  -> detective
  -> safe_done                 if risk_level == "An toàn"
  -> psychology                if risk_level in {"Nghi ngờ", "Nguy hiểm"}
  -> awaiting_situation
  -> responder                 after one of four situation choices
  -> share_card                optional PNG download
```

Code mapping:

- `run_ai_sequence`: detective, optional psychology.
- `state_machine_metrics`: reports `done_safe`, `awaiting_situation`, or `responder_ready`.
- `rescue_plan`: responder state.
- `renderSituation` in `static/js/script.js`: asks the four-choice question only after risky results.

AI call reduction:

- Naive flow: always calls Detective + Cô tâm lý + Người ứng cứu = 3 calls.
- State machine:
  - Safe message: Detective only = 1 call, saves 2.
  - Risky message before situation choice: Detective + Cô tâm lý = 2 calls, saves 1.
  - Responder only after user chooses a crisis state.
  - Duplicate messages use cache and spend 0 new calls.

## Four Crisis Scenarios

- `clicked_link`: user clicked a link or opened a file but has not entered information.
- `shared_info`: user entered personal data, password, OTP, or documents.
- `sent_money`: user transferred money or card/account details.
- `installed_app`: user installed a suspicious app/file or granted device permissions.

## Safety Self-Assessment

- Phone hallucination blocking: enforced by whitelist comparison against `hotlines_verified.json`.
- AI failure mode: responder falls back to verified deterministic templates.
- User choice locking: once a crisis choice is clicked, other choices are disabled.
- High contrast and larger text: persisted in localStorage for older users.
- Share card: generated server-side from current result and product URL; no user secret is embedded.

## New Operator Checklist

1. Copy `.env.example` to `.env`.
2. Set a valid `GEMINI_API_KEY`.
3. Set `PUBLIC_PRODUCT_URL` before public deployment so QR codes point to the production product.
4. Run `pytest -q`.
5. Run `python scripts/run_regression.py`.
6. Run `python scripts/evaluate_quality.py`.
7. Re-check `data/hotlines_verified.json` sources before demos involving emergency guidance.
