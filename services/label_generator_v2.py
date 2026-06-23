from pathlib import Path
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont
import fitz
from .runtime_paths import PROJECT_ROOT, runtime_root


TEMPLATE_PDF = PROJECT_ROOT / "assets" / "label_template.pdf"
CACHE_DIR = runtime_root() / "output" / "_label_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
BG_PNG = CACHE_DIR / "label_template_bg.png"


def rtl(text: str) -> str:
    return get_display(str(text or "").strip())


def get_font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates += [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
        ]
    candidates += [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
    ]

    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass

    raise RuntimeError("No usable font found on this Mac")


def ensure_background():
    if BG_PNG.exists():
        return BG_PNG

    doc = fitz.open(TEMPLATE_PDF)
    page = doc[0]
    mat = fitz.Matrix(2, 2)  # חד מספיק
    pix = page.get_pixmap(matrix=mat, alpha=False)
    pix.save(str(BG_PNG))
    doc.close()
    return BG_PNG


def fit_font(draw, text, max_width, start_size=56, min_size=18, bold=False):
    size = start_size
    while size >= min_size:
        font = get_font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            return font
        size -= 1
    return get_font(min_size, bold=bold)


def draw_centered(draw, box, text, start_size=56, min_size=18, bold=False):
    if not text:
        return
    x1, y1, x2, y2 = box
    max_width = x2 - x1
    font = fit_font(draw, text, max_width, start_size=start_size, min_size=min_size, bold=bold)
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = x1 + ((x2 - x1 - tw) / 2)
    y = y1 + ((y2 - y1 - th) / 2) - 2
    draw.text((x, y), text, font=font, fill="black")


def split_item(text: str, max_chars=24):
    text = str(text or "").strip()
    if not text:
        return "", ""

    if len(text) <= max_chars:
        return text, ""

    cut = text.rfind(" ", 0, max_chars)
    if cut == -1:
        cut = max_chars

    line1 = text[:cut].strip()
    line2 = text[cut:].strip()
    return line1, line2


def generate_label_pdf(data, output="output/label_v2.pdf", debug=False):
    bg_path = ensure_background()
    img = Image.open(bg_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    # קואורדינטות בפיקסלים על רקע 2x
    # שמאל = אזור הערכים בלבד
    BOXES = {
        "customer": (140, 70, 790, 150),
        "address":  (140, 160, 790, 240),
        "contact":  (140, 255, 790, 345),
        "po":       (160, 390, 760, 485),
        "item1":    (120, 500, 800, 585),
        "item2":    (120, 555, 800, 625),
        "qty":      (170, 650, 720, 770),
        "sku":      (150, 760, 760, 870),
    }

    customer = rtl(str(data.get("customer", "")).strip())
    address = rtl(str(data.get("address", "")).strip())
    contact_line = rtl(f'{str(data.get("contact_name", "")).strip()} {str(data.get("phone", "")).strip()}'.strip())
    po_number = str(data.get("po_number", "")).strip()

    product_lines = data.get("product_lines") or []
    product_text = " ".join(str(x).strip() for x in product_lines if str(x).strip())
    item1, item2 = split_item(product_text, max_chars=24)
    item1 = rtl(item1)
    item2 = rtl(item2)

    qty = str(data.get("quantity", "")).strip()
    qty_text = rtl(f"{qty} יח׳" if qty else "")

    sku = str(data.get("sku", "")).strip()
    sku_text = rtl(f"מק״ט {sku}" if sku else "")

    draw_centered(draw, BOXES["customer"], customer, start_size=34, min_size=20)
    draw_centered(draw, BOXES["address"], address, start_size=32, min_size=20)
    draw_centered(draw, BOXES["contact"], contact_line, start_size=30, min_size=18)
    draw_centered(draw, BOXES["po"], po_number, start_size=42, min_size=24)
    draw_centered(draw, BOXES["item1"], item1, start_size=34, min_size=20)
    draw_centered(draw, BOXES["item2"], item2, start_size=26, min_size=18)
    draw_centered(draw, BOXES["qty"], qty_text, start_size=52, min_size=24)
    draw_centered(draw, BOXES["sku"], sku_text, start_size=50, min_size=24, bold=True)

    if debug:
        for box in BOXES.values():
            draw.rectangle(box, outline="red", width=2)

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PDF", resolution=144.0)
    return str(output_path)
