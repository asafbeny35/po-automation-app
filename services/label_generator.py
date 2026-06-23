from io import BytesIO
from pathlib import Path

from bidi.algorithm import get_display
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def _register_fonts():
    candidates = [
        ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "HebBold"),
        ("/Library/Fonts/Arial Bold.ttf", "HebBold"),
        ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", "HebFont"),
        ("/Library/Fonts/Arial Unicode.ttf", "HebFont"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "HebFont"),
        ("/Library/Fonts/Arial.ttf", "HebFont"),
    ]

    found = {}
    for path, name in candidates:
        if Path(path).exists() and name not in found:
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                found[name] = True
            except Exception:
                pass

    regular = "HebFont" if "HebFont" in found else None
    bold = "HebBold" if "HebBold" in found else regular

    if not regular:
        # Hosted Linux runtimes do not have the local Mac font set.
        # Fall back to built-in ReportLab fonts so import-time initialization
        # does not crash the entire API process.
        return "Helvetica", "Helvetica-Bold"

    return regular, bold


FONT_NAME, FONT_BOLD = _register_fonts()


def rtl(text: str) -> str:
    return get_display(str(text or "").strip())


def _fit_text(text: str, max_chars: int) -> str:
    text = str(text or "").strip()
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


def _split_product_lines(text: str, max_len: int = 26):
    text = str(text or "").strip()
    if not text:
        return ["", ""]

    if len(text) <= max_len:
        return [text, ""]

    cut = text.rfind(" ", 0, max_len)
    if cut == -1:
        cut = max_len

    line1 = text[:cut].strip()
    line2 = text[cut:].strip()

    if len(line2) > max_len:
        line2 = line2[: max_len - 1].rstrip() + "…"

    return [line1, line2]


def generate_label_pdf(data, output="output/label.pdf"):
    template_path = "assets/label_template.pdf"
    Path(output).parent.mkdir(parents=True, exist_ok=True)

    customer = _fit_text(data.get("customer", ""), 34)
    address = _fit_text(data.get("address", ""), 28)
    contact_name = _fit_text(data.get("contact_name", ""), 18)
    phone = _fit_text(data.get("phone", ""), 14)
    po_number = str(data.get("po_number", "")).strip()
    quantity = str(data.get("quantity", "")).strip()
    sku = str(data.get("sku", "")).strip()

    product_lines = data.get("product_lines") or []
    product_text = " ".join([str(x).strip() for x in product_lines if str(x).strip()])
    item_line1, item_line2 = _split_product_lines(product_text, max_len=26)

    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=(595, 842))

    # אזור הערכים הראשי
    CENTER_X = 255

    # קווי גובה מכוילים לפי המדבקה הידנית
    Y_CUSTOMER = 756
    Y_ADDRESS = 712
    Y_CONTACT = 643
    Y_PO = 590
    Y_ITEM_1 = 544
    Y_ITEM_2 = 514
    Y_QTY = 435
    Y_SKU = 374

    # לקוח
    c.setFont(FONT_NAME, 20)
    c.drawCentredString(CENTER_X, Y_CUSTOMER, rtl(customer))

    # כתובת
    c.setFont(FONT_NAME, 20)
    c.drawCentredString(CENTER_X, Y_ADDRESS, rtl(address))

    # איש קשר + טלפון באותה שורה
    contact_line = f"{contact_name} {phone}".strip()
    c.setFont(FONT_NAME, 18)
    c.drawCentredString(CENTER_X, Y_CONTACT, rtl(contact_line))

    # מספר הזמנה
    c.setFont(FONT_NAME, 24)
    c.drawCentredString(CENTER_X, Y_PO, po_number)

    # פריט
    c.setFont(FONT_NAME, 22)
    c.drawCentredString(CENTER_X, Y_ITEM_1, rtl(item_line1))

    if item_line2:
        c.setFont(FONT_NAME, 18)
        c.drawCentredString(CENTER_X, Y_ITEM_2, rtl(item_line2))

    # כמות
    qty_text = f"{quantity} יח׳" if quantity else ""
    c.setFont(FONT_NAME, 32)
    c.drawCentredString(CENTER_X, Y_QTY, rtl(qty_text))

    # מק״ט
    sku_text = f"מק״ט {sku}" if sku else ""
    c.setFont(FONT_BOLD, 26)
    c.drawCentredString(CENTER_X, Y_SKU, rtl(sku_text))

    c.save()
    packet.seek(0)

    overlay = PdfReader(packet)
    template = PdfReader(template_path)

    writer = PdfWriter()
    page = template.pages[0]
    page.merge_page(overlay.pages[0])
    writer.add_page(page)

    with open(output, "wb") as f:
        writer.write(f)

    return output
