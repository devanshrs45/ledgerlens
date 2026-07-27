'''
watermark.py -> Adds visible watermark to image:
- Input and Output bytes
- Bottom right position, grey background
- Doc ID + Time (UTC)
- Resize large images
'''

from datetime import datetime, timezone
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

#Adds a watermark containing DocId and Time (UTC) on bottom right of image
def add_visible_watermark(image_bytes: bytes, doc_id: str) -> bytes:
    image = Image.open(BytesIO(image_bytes)).convert("RGBA")    #Wraps bytes and opens it as image
    blank = Image.new("RGBA", image.size, (0, 0, 0, 0))       #new blank image to add watermark
    draw = ImageDraw.Draw(blank)      #adds pen on the blank image to draw on

    #Gets the image dimensions 
    width, height = image.size
    font_size = max(width // 22, 24)    #sets font size based on width

    #selects font style, loads default when error/DejaVuSans not available
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    #doc_id + timestamp as the watermark
    watermark_text = f"{doc_id} | {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"

    #watermark position
    box = draw.textbbox((0, 0), watermark_text, font=font)
    text_w = box[2] - box[0]    #gets text width (right - left)
    #(x, y) coordinates
    x = width - text_w - 30
    y = height - font_size * 2

    draw.rectangle([x - 10, y - 10, x + text_w + 10, y + font_size + 20], fill=(90, 90, 90, 50))   #draws the grey rectangle background on blank
    draw.text((x, y), watermark_text, fill=(255, 255, 255, 140), font=font)             #draws the watermark text on blank

    result = Image.alpha_composite(image, blank).convert("RGB")     #merges blank and image (adds watermark to image)
    #converts back to bytes and returns raw png bytes
    output = BytesIO()
    result.save(output, format="PNG")
    return output.getvalue()


#resize image and shrink large ones
def resize_image(image_bytes: bytes, max_dim: int = 1024) -> bytes:
    image = Image.open(BytesIO(image_bytes))        #reads in bytes
    if max(image.size) > max_dim:       
        image.thumbnail((max_dim, max_dim), Image.LANCZOS)      #resizes if image is larger than max_dim
    output = BytesIO()
    image.convert("RGB").save(output, format="PNG")
    return output.getvalue()        #returns in bytes











# from datetime import datetime, timezone
# from io import BytesIO
# from PIL import Image, ImageDraw, ImageFont

# WATERMARK_OPACITY = 110

# #Default font
# def _load_font(size: int) -> ImageFont.ImageFont:
#     return ImageFont.load_default()

# '''#DejaVuSans
# def _load_font(size:int) -> ImageFont.ImageFont:
#     for candidate in (
#         "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
#         "DejaVuSans.ttf",
#     ):
#         try:
#             return ImageFont.truetype(candidate, size)
#         except OSError:
#             continue
#     return ImageFont.load_default()
# '''


# def add_visible_watermark(image_bytes: bytes, doc_id: str) -> bytes:
#     base = Image.open(BytesIO(image_bytes)).convert("RGBA")
#     overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
#     draw = ImageDraw.Draw(overlay)
#     stamp = f"{doc_id} | {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
#     font_size = max(14, base.width // 50)
#     font = _load_font(font_size)
#     bbox = draw.textbbox((0, 0), stamp, font=font)
#     text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
#     margin = max(8, font_size // 2)
#     pos = (base.width - text_w - margin, base.height - text_h - margin)
#     draw.rectangle(
#         [pos[0] - 4, pos[1] - 4, pos[0] + text_w + 4, pos[1] + text_h + 4],
#         fill=(255, 255, 255, 60)
#     )
#     draw.text(pos, stamp, font=font, fill=(80, 80, 80, WATERMARK_OPACITY))
#     out = Image.alpha_composite(base, overlay).convert("RGB")
#     buf = BytesIO()
#     out.save(buf, format="PNG")
#     return buf.getvalue()


# def resize_image(image_bytes: bytes, max_dim: int = 2048) -> bytes:
#     img = Image.open(BytesIO(image_bytes))
#     if max(img.size) > max_dim:
#         img.thumbnail((max_dim, max_dim), Image.LANCZOS)
#     buf = BytesIO()
#     img.convert("RGB").save(buf, format="PNG")
#     return buf.getvalue()



