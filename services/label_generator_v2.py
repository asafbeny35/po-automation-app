import re
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


_NUM_RUN = re.compile(r"\d[\d.,]*(?:\s?[*xX×/\-]\s?\d[\d.,]*)+")


def _isolate_numeric_runs(text: str) -> str:
    """מידות כמו 181.5*33 נשארות ברצף אחד משמאל לימין בתוך טקסט עברי."""
    return _NUM_RUN.sub(lambda m: "\u2066" + m.group(0) + "\u2069", text)


def rtl(text: str) -> str:
    text = _isolate_numeric_runs(str(text or "").strip())
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


def quantity_display_text(quantity, unit) -> str:
    """שורת הכמות: מספר + יחידה מפורשת מההזמנה, עם נפילה ל-יח׳ מהעידן שקדם
    להעברת היחידה. במדבקה ידנית המספר הוא קו תחתון ("________") להשלמה
    בכתב יד — והיחידה חייבת להופיע אחריו."""
    qty = str(quantity or "").strip()
    explicit_unit = str(unit or "").strip()
    has_unit = any("א" <= c <= "ת" for c in qty)
    if qty and explicit_unit and not has_unit:
        return f"{qty} {explicit_unit}"
    if not qty or has_unit:
        return qty
    return f"{qty} יח׳"


# ---------------------------------------------------------------------------
# עיצוב המדבקה (A4, שחור-לבן להדפסה ברורה). כל הערכים מגיעים מהנתונים; התבנית
# מספקת רק את בלוק החברה (QR + פרטי קשר) והלוגו, שנחתכים מ-label_template.pdf.
# ---------------------------------------------------------------------------
PAGE_W_PT, PAGE_H_PT = 595.0, 842.0
SCALE = 3  # פיקסלים לנקודה
MARGIN = 28.0
COMPANY_NAME = "בן יעקב פתרונות טקסטיל"
COMPANY_TAGLINE = "הבחירה של קבלני הביצוע"
FOOTER_QR_CLIP = (41.5, 419.8, 222.2, 600.5)  # ה-QR בלבד (ללא קווי התבנית)
QR_QUIET_PT = 14.0                          # שוליים לבנים (quiet zone) סביב ה-QR
FOOTER_DETAILS_CLIP = (300, 425, 566, 600)  # פרטי קשר בתבנית
FOOTER_LOGO_CLIP = (36, 641, 487, 817)      # לוגו בן יעקב בתבנית


def _px(v):
    return int(round(v * SCALE))


def _render_template_clip(clip, width_pt):
    """חיתוך אזור מהתבנית (וקטורי) והדפסתו ברזולוציה גבוהה לרוחב נתון."""
    doc = fitz.open(TEMPLATE_PDF)
    try:
        rect = fitz.Rect(*clip)
        zoom = (width_pt * SCALE) / rect.width
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, alpha=False)
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    finally:
        doc.close()


def _ink_rect(clip):
    """הגבולות האמיתיים של הדיו (פיקסלים שאינם לבנים) בתוך אזור בתבנית, בנקודות."""
    doc = fitz.open(TEMPLATE_PDF)
    try:
        rect = fitz.Rect(*clip)
        z = 8.0
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(z, z), clip=rect, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
        bbox = img.point(lambda v: 255 if v < 200 else 0).getbbox()
        if not bbox:
            return rect
        return fitz.Rect(rect.x0 + bbox[0] / z, rect.y0 + bbox[1] / z, rect.x0 + bbox[2] / z, rect.y0 + bbox[3] / z)
    finally:
        doc.close()


def _tight_ink_bbox(image):
    """תיבת הגבול של פיקסלים כהים (אותו סף שבו נמדדת התוצאה הסופית)."""
    return image.convert("L").point(lambda v: 255 if v < 128 else 0).getbbox()


def _render_ink_to_height(clip, height_px):
    """מציג את הדיו של האזור בגובה מדויק בפיקסלים (יחס גובה-רוחב נשמר)."""
    ink = _ink_rect(clip)
    doc = fitz.open(TEMPLATE_PDF)
    try:
        zoom = height_px / ink.height
        pix = doc[0].get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=ink, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        if img.height != height_px:
            img = img.resize((img.width, height_px), Image.LANCZOS)
        return img
    finally:
        doc.close()


def _text_w(draw, text, font, rtl_text=True):
    kw = _RTL_KWARGS if rtl_text else {}
    b = draw.textbbox((0, 0), text, font=font, **kw)
    return b[2] - b[0]


def _fit(draw, text, max_w, start, min_size, bold=False, rtl_text=True):
    size = _px(start)
    floor = _px(min_size)
    while size >= floor:
        font = get_font(size, bold=bold)
        if _text_w(draw, text, font, rtl_text) <= max_w:
            return font
        size -= 2
    return get_font(floor, bold=bold)


def _wrap_logical(draw, logical_text, max_w, font, max_lines):
    """שבירת שורות על הטקסט הלוגי (לפני bidi); השורה האחרונה מקבלת את כל השאר."""
    words = str(logical_text or "").split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and _text_w(draw, rtl(trial), font) > max_w and len(lines) < max_lines - 1:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _put(draw, x_right, y_top, text, font, bold=False, rtl_text=True, anchor="right", cx=None):
    """ציור טקסט; ליישור לימין x_right הוא הקצה הימני, ל-center משתמשים ב-cx."""
    kw = _RTL_KWARGS if rtl_text else {}
    b = draw.textbbox((0, 0), text, font=font, **kw)
    w, h = b[2] - b[0], b[3] - b[1]
    if anchor == "center":
        x = cx - w / 2 - b[0]
    else:
        x = x_right - w - b[0]
    y = y_top - b[1]
    sw = max(1, int(font.size / 38)) if bold else 0  # הדגשה סינתטית; גופן עברי מודגש לא מצורף
    draw.text((x, y), text, font=font, fill="black", stroke_width=sw, stroke_fill="black", **kw)
    return h


def _card(draw, box_pt, label, radius=10, label_font=None):
    x1, y1, x2, y2 = [_px(v) for v in box_pt]
    draw.rounded_rectangle((x1, y1, x2, y2), radius=_px(radius), outline="black", width=_px(1.6))
    if label:
        # תווית קטנה בפינה הימנית-עליונה של הכרטיס
        font = label_font or get_font(_px(14), bold=True)
        _put(draw, x2 - _px(12), y1 + _px(8), rtl(label), font)


def generate_label_pdf(data, output="output/label_v2.pdf", debug=False):
    W, H = _px(PAGE_W_PT), _px(PAGE_H_PT)
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    left, right = MARGIN, PAGE_W_PT - MARGIN
    inner_pad = 14.0

    customer = str(data.get("customer", "")).strip()
    address = str(data.get("address", "")).strip()
    contact_line = f'{str(data.get("contact_name", "")).strip()} {str(data.get("phone", "")).strip()}'.strip()
    po_number = str(data.get("po_number", "")).strip()
    product_text = " ".join(str(x).strip() for x in (data.get("product_lines") or []) if str(x).strip())
    qty_text = quantity_display_text(data.get("quantity"), data.get("unit"))
    sku = str(data.get("sku", "")).strip()

    label_font = get_font(_px(14), bold=True)

    # ── כותרת: לוגו בשמאל למעלה; מימין, באותו גובה, שם החברה (מודגש) ושורת הסלוגן ──
    logo_w = 150.0
    logo = _render_template_clip(FOOTER_LOGO_CLIP, logo_w)
    header_top = MARGIN
    img.paste(logo, (_px(left), _px(header_top)))
    header_h = logo.height / SCALE
    name_txt = rtl(COMPANY_NAME)
    name_font = _fit(draw, name_txt, _px(right - left - logo_w - 20), 27, 16, bold=True)
    tag_txt = rtl(COMPANY_TAGLINE)
    tag_font = _fit(draw, tag_txt, _px(right - left - logo_w - 20), 19, 12)
    nb = draw.textbbox((0, 0), name_txt, font=name_font, **_RTL_KWARGS)
    tb = draw.textbbox((0, 0), tag_txt, font=tag_font, **_RTL_KWARGS)
    name_h, tag_h, gap = (nb[3] - nb[1]) / SCALE, (tb[3] - tb[1]) / SCALE, 9.0
    y_start = header_top + (header_h - (name_h + gap + tag_h)) / 2   # גוש הטקסט ממורכז לגובה הלוגו
    _put(draw, _px(right), _px(y_start), name_txt, name_font, bold=True)
    _put(draw, _px(right), _px(y_start + name_h + gap), tag_txt, tag_font)

    # ── לקוח / כתובת / איש קשר ───────────────────────────────────────────────
    top = header_top + header_h + 14
    box = (left, top, right, top + 164)
    _card(draw, box, "לקוח", label_font=label_font)
    inner_w = _px(right - left - 2 * inner_pad)
    xr = _px(right - inner_pad)
    f = _fit(draw, rtl(customer), inner_w, 34, 20, bold=True)
    _put(draw, xr, _px(top + 30), rtl(customer), f, bold=True)
    f = _fit(draw, rtl(address), inner_w, 21, 14)
    _put(draw, xr, _px(top + 84), rtl(address), f)
    f = _fit(draw, rtl(contact_line), inner_w, 21, 14)
    _put(draw, xr, _px(top + 122), rtl(contact_line), f)
    # קו דק בין שם הלקוח לפרטים
    draw.line((_px(left + inner_pad), _px(top + 76), _px(right - inner_pad), _px(top + 76)), fill="black", width=_px(0.6))

    # ── מספר הזמנה | מק״ט ────────────────────────────────────────────────────
    row_top = top + 164 + 12
    row_h = 100
    mid = left + (right - left) * 0.5
    po_box = (mid + 6, row_top, right, row_top + row_h)
    sku_box = (left, row_top, mid - 6, row_top + row_h)
    _card(draw, po_box, "מספר הזמנה", label_font=label_font)
    _card(draw, sku_box, "מק״ט", label_font=label_font)
    for bx, txt, size, min_size in ((po_box, po_number, 32, 16), (sku_box, sku, 34, 16)):
        if not txt:
            continue
        bw = _px(bx[2] - bx[0] - 2 * inner_pad)
        f = _fit(draw, txt, bw, size, min_size, bold=True, rtl_text=False)
        _put(draw, 0, _px(bx[1] + 40), txt, f, bold=True, rtl_text=False, anchor="center", cx=_px((bx[0] + bx[2]) / 2))

    # ── פריט ─────────────────────────────────────────────────────────────────
    item_top = row_top + row_h + 12
    item_h = 120
    item_box = (left, item_top, right, item_top + item_h)
    _card(draw, item_box, "פריט", label_font=label_font)
    max_w = _px(right - left - 2 * inner_pad)
    start = 26
    chosen = None
    for size in range(start, 14, -2):
        font = get_font(_px(size))
        lines = _wrap_logical(draw, product_text, max_w, font, 2)
        if all(_text_w(draw, rtl(l), font) <= max_w for l in lines):
            chosen = (font, lines, size)
            break
    if chosen is None:
        font = get_font(_px(14))
        chosen = (font, _wrap_logical(draw, product_text, max_w, font, 2), 14)
    font, lines, size = chosen
    line_h = size * 1.3
    block_h = line_h * len(lines)
    y0 = item_top + 28 + max(0, (item_h - 28 - 10 - block_h) / 2)
    for i, line in enumerate(lines):
        _put(draw, xr, _px(y0 + i * line_h), rtl(line), font)

    # ── כמות ─────────────────────────────────────────────────────────────────
    qty_top = item_top + item_h + 12
    qty_h = 104
    qty_box = (left, qty_top, right, qty_top + qty_h)
    _card(draw, qty_box, "כמות", label_font=label_font)
    if qty_text:
        f = _fit(draw, rtl(qty_text), inner_w, 46, 20, bold=True)
        _put(draw, 0, _px(qty_top + 34), rtl(qty_text), f, bold=True, anchor="center", cx=_px((left + right) / 2))

    # ── פס מפריד + פרטי החברה (QR, איש קשר) + לוגו ───────────────────────────
    footer_top = qty_top + qty_h + 14
    draw.line((_px(left), _px(footer_top), _px(right), _px(footer_top)), fill="black", width=_px(1.6))
    # QR והלוגו מיושרים לשמאל; פרטי החברה (טקסט) בצד ימין. ה-QR נחתך עם שוליים לבנים (quiet zone).
    qr_w = 128.0
    qr_core = _render_template_clip(FOOTER_QR_CLIP, qr_w)
    pad = _px(QR_QUIET_PT)
    qr = Image.new("RGB", (qr_core.width + 2 * pad, qr_core.height + 2 * pad), "white")
    qr.paste(qr_core, (pad, pad))
    qr_y = footer_top + 8
    img.paste(qr, (_px(left) - pad, _px(qr_y)))   # גבול ה-QR עצמו מיושר לשוליים השמאליים
    # גוש הטקסט (מ"בן יעקב" ועד האימייל): גובה הדיו זהה בדיוק לגובה ה-QR, ושני הקצוות מיושרים
    qr_ink = _tight_ink_bbox(qr_core)          # גבולות הדיו האמיתיים של ה-QR בפיקסלים
    qr_top_px = _px(qr_y) + pad + qr_ink[1]
    qr_ink_h = qr_ink[3] - qr_ink[1]
    details = _render_ink_to_height(FOOTER_DETAILS_CLIP, qr_ink_h)
    d_ink = _tight_ink_bbox(details)
    details = details.crop(d_ink)               # רק הדיו, כדי שהקצוות יהיו מדויקים
    if details.height != qr_ink_h:
        details = details.resize((details.width, qr_ink_h), Image.LANCZOS)
    img.paste(details, (_px(right) - details.width, qr_top_px))
    if debug:
        for b in (box, po_box, sku_box, item_box, qty_box):
            draw.rectangle([_px(v) for v in b], outline="red", width=2)

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PDF", resolution=72.0 * SCALE)
    return str(output_path)
