import qrcode
import io
import os
from PIL import Image
from aiogram.types import BufferedInputFile

BG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "qr_bg.png")


def generate_qr(data: str) -> BufferedInputFile:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="#1a1a2e", back_color="#ffffff").convert("RGBA")

    if os.path.exists(BG_PATH):
        bg = Image.open(BG_PATH).convert("RGBA")
        bg_w, bg_h = bg.size

        qr_w, qr_h = qr_img.size
        scale = min((bg_w * 0.65) / qr_w, (bg_h * 0.65) / qr_h)
        new_w = int(qr_w * scale)
        new_h = int(qr_h * scale)
        qr_img = qr_img.resize((new_w, new_h), Image.LANCZOS)

        x = (bg_w - new_w) // 2
        y = (bg_h - new_h) // 2

        bg.paste(qr_img, (x, y), qr_img)
        final = bg.convert("RGB")
    else:
        final = qr_img.convert("RGB")

    buffer = io.BytesIO()
    final.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return BufferedInputFile(buffer.getvalue(), filename="qr.png")
