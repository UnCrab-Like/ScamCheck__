# AI Evidence And Quality Report

## Current API Status

The app is integrated with Gemini through `call_gemini_json` in `app.py`.

Latest live check result:

```text
Gemini returned API_KEY_INVALID.
```

This means the code path exists, but the demo environment needs a valid `GEMINI_API_KEY` before capturing final live Gemini screenshots.

## How To Capture Required AI Evidence

1. Put a valid key in `.env`.
2. Run `python app.py`.
3. Open the browser devtools Network tab.
4. Submit each sample below.
5. Save screenshots of:
   - request route `/scam_check`
   - returned JSON result
   - UI rendering

## Three Required Message Types

### 1. Safe Message

```text
Me oi toi nay con ve muon 30 phut vi hop lop keo dai.
```

Expected behavior:

- Thám tử returns `An toàn`.
- Cô tâm lý is not called.
- Người ứng cứu is not shown.

### 2. Suspicious Message

```text
Chuc mung bac da trung thuong qua lon, bam link de nhan thuong trong hom nay.
```

Expected behavior:

- Thám tử returns `Nghi ngờ`.
- Cô tâm lý explains urgency/reward pressure.
- User can choose a crisis state if they acted.

### 3. Dangerous Message

```text
Tai khoan ngan hang cua ban bi khoa. Xac minh OTP tai http://bank-secure.example ngay.
```

Expected behavior:

- Thám tử returns `Nguy hiểm`.
- Rule indicators include OTP and suspicious link.
- Cô tâm lý appears.
- Responder flow is available.

## Quality Measurement

Command:

```bash
source .venv/bin/activate
python scripts/evaluate_quality.py
```

Latest measured output:

```text
Before rule/domain improvements: 66.67% accuracy
After rule/domain improvements: 98.33% accuracy
Coverage: 100.00%
```

Confusion matrix after improvements:

```text
Expected \ Predicted | An toàn | Nghi ngờ | Nguy hiểm
An toàn              | 20      | 0       | 0
Nghi ngờ             | 0       | 19      | 1
Nguy hiểm            | 0       | 0       | 20
```

Known weaknesses:

- Small-fee messages can sit between `Nghi ngờ` and `Nguy hiểm`.
- Short-link expansion depends on network availability.
- The app analyzes text only, not screenshots/images.
