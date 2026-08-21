import base64
from io import BytesIO
from PIL import Image

MAX_DIMENSION = 1024


def extract_from_image(file_path: str) -> dict:
    img = Image.open(file_path)
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    width, height = img.size
    if max(width, height) > MAX_DIMENSION:
        ratio = MAX_DIMENSION / max(width, height)
        new_size = (int(width * ratio), int(height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {
        "base64": b64,
        "width": img.size[0],
        "height": img.size[1],
        "original_width": width,
        "original_height": height,
    }
