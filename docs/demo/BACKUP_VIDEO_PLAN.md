# Backup Demo Video Plan

Goal: create a video under 5 minutes that can be played offline if the network fails.

## Recording Checklist

- Use a quiet room and a single narrator.
- Record the browser window and terminal.
- Keep the video under 5 minutes.
- Export as MP4.
- Store the final file outside git if it is large, and bring it on a USB drive or laptop.

## Suggested Timeline

### 0:00-0:20

Show app home screen and legal footer.

### 0:20-1:20

Run main scam check with the banking OTP sample.

### 1:20-2:00

Show technical indicators:

- OTP rule
- fake/suspicious domain
- highlighted quote

### 2:00-3:00

Show crisis responder:

- select `Đã chuyển tiền`
- show numbered steps
- show verified hotline note

### 3:00-3:40

Show share card download and QR image.

### 3:40-4:20

Show high contrast and large text.

### 4:20-4:50

Show terminal:

```bash
pytest -q
python scripts/evaluate_quality.py
```

### 4:50-5:00

Close with measured accuracy and safety message.

## Offline Fallback

If Gemini key or internet fails during recording, use cached/demo results and explicitly say:

"The deterministic layers, responder flow, hotline filter, share card, and tests run offline. Live Gemini evidence should be captured again after setting a valid key."
