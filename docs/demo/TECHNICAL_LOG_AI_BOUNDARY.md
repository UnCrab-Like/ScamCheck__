# Technical Log And AI Boundary

## What AI Generates At Runtime

Gemini is used for:

- Thám tử structured analysis.
- Cô tâm lý explanation.
- Người ứng cứu step wording when available.

Every AI response is constrained:

- JSON schemas are used.
- Parsers apply defaults if output is malformed.
- Rule indicators are merged after AI.
- Risk floor prevents obvious unsafe messages being downgraded.
- Responder phone numbers are filtered against `data/hotlines_verified.json`.

## What The Team Controls In Code

The team controls:

- UI layout and accessibility controls.
- Prompt templates.
- JSON schemas.
- URL regex extraction.
- Short-link logic.
- Fake-domain algorithm.
- Rule-based indicators.
- Evaluation datasets and scripts.
- Hotline table.
- Responder fallback templates.
- Phone hallucination filter.
- Share-card generation.
- Tests and documentation.

## Key Decisions

### 1. Do not rely on AI alone

Reason: scam messages often contain deterministic signals such as OTP, APK, fake domains, and urgent payment wording.

Implementation:

- `rule_indicators`
- `baseline_risk_level`
- `merge_rule_indicators`

### 2. Keep hotline numbers outside prompts

Reason: phone numbers are safety-critical and must be auditable.

Implementation:

- `data/hotlines_verified.json`
- `load_hotlines`
- `sanitize_phone_hallucinations`

### 3. Use state machine instead of always calling all roles

Reason: reduce latency and AI cost.

Implementation:

- safe messages skip Cô tâm lý and Người ứng cứu
- risky messages call Cô tâm lý
- Người ứng cứu waits for one of four user choices
- duplicate messages use cache

### 4. Make failure modes useful

Reason: demo and user safety should not collapse when Gemini fails.

Implementation:

- defensive parser defaults
- responder verified fallback templates
- invalid-key message
- offline evaluator and tests

## Bugs Encountered

- Early Gemini endpoint/shape was placeholder and incorrect; replaced with Google Generative Language API.
- API timeout originally used a thread wrapper that could hang during DNS/network failure; replaced with direct `requests.post` timeout.
- Dark mode initially only changed the page background; fixed by replacing hard-coded light surfaces with CSS variables.
- Rule detector initially over-flagged the word `shipper`; narrowed the rule to payment/link context.
- Evaluator exposed missing cases for `chuyen khoan`, `phi ho so`, `can cuoc`, and `link chat`; rules were updated and accuracy improved.

## Current Open Risk

The current `.env` key returned `API_KEY_INVALID` during live checking. A valid key is needed before final live Gemini screenshots.
