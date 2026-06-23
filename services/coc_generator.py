from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT
from datetime import datetime
from pathlib import Path


def generate_coc_pdf(po, output_path: str, logo_path: str):
    doc = SimpleDocTemplate(output_path, pagesize=A4)

    styles = getSampleStyleSheet()

    rtl_style = ParagraphStyle(
        name="RTL",
        parent=styles["Normal"],
        alignment=TA_RIGHT,
        fontName="Helvetica",
        fontSize=10,
        leading=14,
    )

    title_style = ParagraphStyle(
        name="TitleRTL",
        parent=rtl_style,
        fontSize=14,
        leading=18,
    )

    elements = []

    # Logo
    if logo_path and Path(logo_path).exists():
        elements.append(Image(logo_path, width=120, height=60))
        elements.append(Spacer(1, 10))

    now = datetime.now()

    today_str = now.strftime("%d/%m/%Y")
    expiry_year = now.year + 8
    expiry_str = f"{now.strftime('%m')}/{expiry_year}"
    batch_str = f"{now.strftime('%m')}{now.strftime('%m')}/{now.year}"

    item = po.items[0] if po.items else None

    elements.append(Paragraph(f"C.O.C עבור הזמנה מספר: {po.po_number}", title_style))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(f"תאריך: {today_str}", rtl_style))
    elements.append(Paragraph("שם הספק: בן יעקב פתרונות טקסטיל", rtl_style))
    elements.append(Paragraph(f"מק״ט פריט: {item.sku if item else ''}", rtl_style))
    elements.append(Paragraph(f"תוקף: {expiry_str}", rtl_style))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("תיאור הפריט:", rtl_style))
    elements.append(Paragraph(item.description if item else "", rtl_style))
    elements.append(Spacer(1, 10))

    qty = item.quantity if item else ""
    rolls = max(int(getattr(po, "rolls", 1) or 1), 1)
    elements.append(Paragraph(f"כמות: {qty} מ״ר | אספקה ב {rolls} גלילים", rtl_style))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph(
        "1. אנו מאשרים בזאת שהפריטים המפורטים לעיל המסופקים לכם עומדים בכל הדרישות המופיעות במפרט המתואר בהזמנה.",
        rtl_style
    ))
    elements.append(Paragraph(
        "2. הפריטים שסופקו לכם נבדקו על ידי היצרן ועומדים בכל הדרישות הרלוונטיות.",
        rtl_style
    ))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph(f"מס׳ מנה: {batch_str}", rtl_style))

    doc.build(elements)
