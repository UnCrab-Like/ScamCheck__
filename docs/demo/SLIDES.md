# ScamCheck Demo Slides

## Slide 1: ScamCheck

Check suspicious messages before clicking, sending OTP, transferring money, or installing unknown apps.

Legal: ScamCheck is for reference only and does not replace legal, financial, or official authority advice.

## Slide 2: Problem

Scam messages pressure users to act fast.

Older users are especially exposed to fake banks, fake police, fake delivery, prize scams, short links, and APK files.

## Slide 3: Solution

ScamCheck combines AI and deterministic safety rules.

Three roles:

- Thám tử: risk and evidence.
- Cô tâm lý: explains the manipulation.
- Người ứng cứu: crisis steps after user chooses what happened.

## Slide 4: Main Demo Flow

1. Paste a suspicious message.
2. Thám tử returns risk, indicators, quotes, and actions.
3. Cô tâm lý explains the psychological trick for risky messages.
4. User selects crisis state.
5. Người ứng cứu gives numbered steps and sample sentences.

## Slide 5: Technical Highlights

- Structured Gemini JSON schemas.
- Defensive parser for malformed AI output.
- Prompt-injection guard and risk floor.
- Regex URL extraction and short-link resolution.
- Fake-domain detection with homograph normalization and Levenshtein distance.
- Rule indicators merged with AI output.

## Slide 6: Safety Highlights

- Verified hotline table in repo.
- AI cannot invent phone numbers shown to users.
- Phone-number whitelist filter blocks unverified numbers.
- Duplicate result cache reduces repeated calls.
- High-contrast and large-text modes for older users.

## Slide 7: Quality Measurement

Evaluation set:

- 60 labeled messages.
- Balanced labels: An toàn, Nghi ngờ, Nguy hiểm.
- 15 hard ambiguous cases.

Measured result:

- Before technical rules: 66.67% accuracy.
- After technical rules: 98.33% accuracy.
- Coverage: 100%.

## Slide 8: Crisis Response

Four situations:

- Clicked a link or opened a file.
- Shared information, OTP, password, or documents.
- Sent money.
- Installed an unknown app.

Each scenario has different steps and sample words to say.

## Slide 9: Lessons

- AI is useful for explanation, but deterministic rules are needed for safety.
- Phone numbers must come from verified data, not AI text.
- Measuring false positives and false negatives changed the implementation.
- A demo-ready product needs offline fallback: docs, scripts, tests, and video.
