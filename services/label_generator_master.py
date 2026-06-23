from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from bidi.algorithm import get_display

BASE_DIR = Path(__file__).resolve().parent.parent
BG_PATH = BASE_DIR / "assets" / "label_master.png"


def rtl(text):
    return get_display(str(text or "").strip())


def get_font(size):
    paths = [
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    raise RuntimeError("No font found")


def draw_center(draw, box, text, size):
    x1, y1, x2, y2 = box
    font = get_font(size)
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = x1 + (x2 - x1 - w) / 2
    y = y1 + (y2 - y1 - h) / 2
    draw.text((x, y), text, font=font, fill="black")


def generate_label_pdf(data, output="output/label_master.pdf"):
    img = Image.open(BG_PATH).convert("RGB")
    draw = ImageDraw.Draw(img)

    # 🔥 אזורים מדויקים לפי התמונה שסימנת
    BOXES = {
        "customer": (120, 40, 600, 100),
        "address":  (120, 110, 600, 170),
        "contact":  (120, 180, 600, 240),

        "po":       (120, 320, 600, 380),
        "item":     (120, 380, 600, 460),
        "qty":      (120, 460, 600, 540),

        "sku":      (120, 580, 600, 650),
    }

    # נתונים
    customer = rtl(data.get("customer"))
    address = rtl(data.get("address"))
    contact = rtl(f'{data.get("contact_name")} {data.get("phone")}')
    po = data.get("po_number")

    item = rtl(" ".join(data.get("product_lines", [])))
    qty = rtl(f'{data.get("quantity")} יח׳')
    sku = rtl(f'מק״ט {data.get("sku")}')

    # ציור
    draw_center(draw, BOXES["customer"], customer, 28)
    draw_center(draw, BOXES["address"], address, 26)
    draw_center(draw, BOXES["contact"], contact, 24)

    draw_center(draw, BOXES["po"], po, 32)
    draw_center(draw, BOXES["item"], item, 28)
    draw_center(draw, BOXES["qty"], qty, 36)
    draw_center(draw, BOXES["sku"], sku, 34)

    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PDF")

    return str(out)
