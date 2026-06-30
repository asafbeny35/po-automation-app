from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, features as pil_features
from PIL.ImageFont import Layout as FontLayout
import fitz
from .runtime_paths import PROJECT_ROOT, runtime_root

try:
    from bidi.algorithm import get_display as _bidi_get_display
    _HAS_BIDI = True
except ImportError:
    _HAS_BIDI = False

_HAS_RAQM = pil_features.check_feature("raqm")
_FONT_LAYOUT = FontLayout.RAQM if _HAS_RAQM else FontLayout.BASIC
_RTL_KWARGS = {"direction": "rtl", "language": "he"} if _HAS_RAQM else {}

TEMPLATE_PDF = PROJECT_ROOT / "assets" / "label_template.pdf"
BUNDLED_FONT = PROJECT_ROOT / "assets" / "NotoSansHebrew-Regular.ttf"
CACHE_DIR = runtime_root() / "output" / "_label_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
BG_PNG = CACHE_DIR / "label_template_bg.png"


def rtl(text: str) -> str:
    text = str(text or "").strip()
    if _HAS_RAQM:
        return text  # RAQM handles RTL shaping and direction natively
    if _HAS_BIDI:
        return _bidi_get_display(text)
    return text


def get_font(size: int, bold: bool = False):
    # Bundled font always comes first — guaranteed Hebrew support on any environment
    candidates = [str(BUNDLED_FONT)]
    if bold:
        candidates += [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/Library/Fonts/Arial Bold.ttf",
            "/usr/share/fonts/opentype/noto/NotoSansHebrew-Bold.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansHebrew-Bold.ttf",
        ]
    candidates += [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansHebrew-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansHebrew-Regular.ttf",
    ]

    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size, layout_engine=_FONT_LAYOUT)
            except Exception:
                pass

    try:
        return ImageFont.load_default()
    except Exception as exc:
        raise RuntimeError("No usable font found for label generation") from exc


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


def fit_font(draw, text, max_width, start_size=56, min_size=18, bold=False, rtl_text=False):
    size = start_size
    kw = _RTL_KWARGS if rtl_text else {}
    while size >= min_size:
        font = get_font(size, bold=bold)
        bbox = draw.textbbox((0, 0), text, font=font, **kw)
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


def draw_rtl(draw, box, text, start_size=56, min_size=18, bold=False):
    """ציור עברית RTL אמיתי — RAQM כשזמין, bidi כ-fallback."""
    if not text:
        return
    x1, y1, x2, y2 = box
    max_width = x2 - x1
    font = fit_font(draw, text, max_width, start_size=start_size, min_size=min_size, bold=bold, rtl_text=True)
    bbox = draw.textbbox((0, 0), text, font=font, **_RTL_KWARGS)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = x2 - tw
    y = y1 + ((y2 - y1 - th) / 2) - 2
    draw.text((x, y), text, font=font, fill="black", **_RTL_KWARGS)


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
    BOXES = {
        "customer": (140, 70,  790, 155),
        "address":  (140, 162, 790, 242),
        "contact":  (140, 252, 790, 342),
        "po":       (160, 392, 760, 472),
        "item1":    (120, 492, 800, 562),  # שורת פריט — שורה אחת, גופן מתכווץ לפי הצורך
        "item2":    (120, 492, 800, 562),  # לא בשימוש (מכוסה ע"י item1)
        "qty":      (140, 564, 680, 630),  # שורת כמות
        "sku":      (140, 648, 590, 742),  # שורת מק"ט — מעל קו הברקוד
    }

    customer = rtl(str(data.get("customer", "")).strip())
    address = rtl(str(data.get("address", "")).strip())
    contact_line = rtl(f'{str(data.get("contact_name", "")).strip()} {str(data.get("phone", "")).strip()}'.strip())
    po_number = str(data.get("po_number", "")).strip()

    product_lines = data.get("product_lines") or []
    product_text = " ".join(str(x).strip() for x in product_lines if str(x).strip())
    item1 = rtl(product_text)  # שורה אחת, גופן מתכווץ אוטומטית
    item2 = ""

    qty = str(data.get("quantity", "")).strip()
    qty_text = rtl(f"{qty} יח׳" if qty else "")

    sku = str(data.get("sku", "")).strip()
    sku_text = sku  # מספר — לא צריך bidi

    draw_rtl(draw, BOXES["customer"], customer, start_size=44, min_size=24)
    draw_rtl(draw, BOXES["address"], address, start_size=42, min_size=24)
    draw_rtl(draw, BOXES["contact"], contact_line, start_size=38, min_size=22)
    draw_centered(draw, BOXES["po"], po_number, start_size=48, min_size=28)
    draw_rtl(draw, BOXES["item1"], item1, start_size=38, min_size=22)
    draw_rtl(draw, BOXES["item2"], item2, start_size=32, min_size=20)
    draw_rtl(draw, BOXES["qty"], qty_text, start_size=36, min_size=22)
    draw_centered(draw, BOXES["sku"], sku_text, start_size=58, min_size=30, bold=True)

    if debug:
        for box in BOXES.values():
            draw.rectangle(box, outline="red", width=2)

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PDF", resolution=144.0)
    return str(output_path)
