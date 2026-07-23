"""Share-card image and QR rendering."""

from __future__ import annotations

import os
from io import BytesIO
from typing import Any

def product_url() -> str:
    """Return the public product address encoded into generated QR codes."""
    return os.getenv("PUBLIC_PRODUCT_URL", "http://127.0.0.1:5000/")


def render_share_card(result: dict[str, Any]) -> BytesIO:
    """Render a mobile-shareable PNG summarizing the primary risk finding."""
    import qrcode
    from PIL import Image, ImageDraw, ImageFont

    detective = result.get("detective", result)
    risk = str(detective.get("risk_level", "Nghi ngờ"))
    indicators = detective.get("indicators", [])
    main_indicator = "Cần kiểm tra thêm."
    if indicators:
        main_indicator = str(indicators[0].get("label", main_indicator))

    bg = {"An toàn": "#d9f2e2", "Nghi ngờ": "#fff1b8", "Nguy hiểm": "#ffd9d7"}.get(risk, "#fff1b8")
    fg = {"An toàn": "#0b5d2a", "Nghi ngờ": "#6f4d00", "Nguy hiểm": "#8a1711"}.get(risk, "#6f4d00")
    image = Image.new("RGB", (1080, 1080), bg)
    draw = ImageDraw.Draw(image)
    font_big = ImageFont.load_default(size=72)
    font_mid = ImageFont.load_default(size=42)
    font_small = ImageFont.load_default(size=30)

    draw.rounded_rectangle((54, 54, 1026, 1026), radius=24, fill="#ffffff", outline=fg, width=6)
    draw.text((90, 95), "ScamCheck", fill="#1459a8", font=font_mid)
    draw.text((90, 190), f"Mức rủi ro: {risk}", fill=fg, font=font_big)
    draw.text((90, 330), "Dấu hiệu chính:", fill="#18212f", font=font_mid)

    words = main_indicator.split()
    lines = []
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if len(candidate) > 34:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    for idx, line_text in enumerate(lines[:4]):
        draw.text((90, 390 + idx * 52), line_text, fill="#18212f", font=font_mid)

    qr = qrcode.make(product_url()).resize((260, 260))
    image.paste(qr, (730, 720))
    draw.text((90, 740), "Gửi ảnh này cho người thân để cùng kiểm tra.", fill="#18212f", font=font_small)
    draw.text((90, 820), "Quét mã để mở ScamCheck.", fill="#18212f", font=font_small)
    draw.text((90, 950), "Không thay thế tư vấn pháp lý/tài chính.", fill="#596578", font=font_small)

    output = BytesIO()
    image.save(output, format="PNG")
    output.seek(0)
    return output
