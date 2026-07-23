from datetime import datetime, timezone
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

WATERMARK_OPACITY = 110

#Default font
def _load_font(size: int) -> ImageFont.ImageFont:
    return ImageFont.load_default()

'''#DejaVuSans
def _load_font(size:int) -> ImageFont.ImageFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "DejaVuSans.ttf",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()
'''


def apply_watermark(image_bytes: bytes, doc_id: str) -> bytes:
    base = Image.open(BytesIO(image_bytes)).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    stamp = f"{doc_id} | {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
    font_size = max(14, base.width // 50)
    font = _load_font(font_size)
    bbox = draw.textbbox((0, 0), stamp, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    margin = max(8, font_size // 2)
    pos = (base.width - text_w - margin, base.height - text_h - margin)
    draw.rectangle(
        [pos[0] - 4, pos[1] - 4, pos[0] + text_w + 4, pos[1] + text_h + 4],
        fill=(255, 255, 255, 60)
    )
    draw.text(pos, stamp, font=font, fill=(80, 80, 80, WATERMARK_OPACITY))
    out = Image.alpha_composite(base, overlay).convert("RGB")
    buf = BytesIO()
    out.save(buf, format="PNG")
    return buf.getvalue()


def resize_for_vision(image_bytes: bytes, max_dim: int = 2048) -> bytes:
    img = Image.open(BytesIO(image_bytes))
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    buf = BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()



