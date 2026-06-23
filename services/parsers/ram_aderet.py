import re

from services.models import POItem
from services.parsers.common import sanitize_contact_pair


CUSTOMER_NAME = 'רם אדרת הנדסה אזרחית בע"מ'


def parse(text: str):
    if "רם אדרת" not in text and "תרדא םר" not in text:
        return None

    header = {
        "customer_email": "",
        "customer_id": "",
        "po_number": "",
        "po_date": "",
        "subtotal": 0.0,
        "vat": 0.0,
        "total": 0.0,
        "payment_terms_days": None,
        "payment_terms_label": "",
        "project": "",
        "delivery_address": "",
        "contact_name": "",
        "contact_phone": "",
        "customer_phone": "",
    }

    m = re.search(r"([0-9]{9})\s*:\s*פ\.ח", text)
    if m:
        header["customer_id"] = m.group(1)

    if not header["customer_id"]:
        m = re.search(r"([0-9]{9})\s*:\s*השרומ קסוע", text)
        if m:
            header["customer_id"] = m.group(1)

    m = re.search(r"([0-9]{9})\s*:\s*השרומ קסוע \.סמ", text)
    if m:
        supplier_id = m.group(1)
        if not header["customer_id"] or header["customer_id"] == supplier_id:
            header["customer_id"] = header["customer_id"] or supplier_id

    m = re.search(r"([A-Z0-9\-]+)\s+רפסמ שכר תנמזה", text)
    if m:
        value = m.group(1)
        header["po_number"] = value if value.startswith("PO") else value[::-1]

    m = re.search(r"(\d{2}/\d{2}/\d{2})\s*:\s*הנמזה ךיראת", text)
    if m:
        dd, mm, yy = m.group(1).split("/")
        header["po_date"] = f"{dd}/{mm}/20{yy}"

    m = re.search(r"([0-9\-]+)\s*:\s*סקפ\s*,\s*([0-9\-]+)\s*:\s*ןופלט", text)
    if m:
        header["customer_phone"] = m.group(2)

    m = re.search(r"([^\n]+)\s*:\s*טקיורפ", text)
    if m:
        header["project"] = m.group(1)[::-1].strip()

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if "ליטסקט תונורתפ בקעי ןב" not in line:
            continue
        project_line = line.split("ליטסקט תונורתפ בקעי ןב", 1)[0].strip()[::-1]
        if project_line:
            header["delivery_address"] = project_line

        if index + 1 < len(lines):
            street_line = lines[index + 1].replace("34 ןרוגה", "").strip()[::-1].strip()
            if street_line:
                header["delivery_address"] = f"{header['delivery_address']}, {street_line}".strip(", ")
        if index + 2 < len(lines):
            contact_match = re.search(r"([0-9\-]+)\s+(.+?):רשק שיא", lines[index + 2])
            if contact_match:
                header["contact_phone"] = contact_match.group(1)
                header["contact_name"] = contact_match.group(2)[::-1].strip()
        break

    header["delivery_address"] = re.sub(r"תאריך הדפסה[:\s]*[0-9/: ]+", "", header["delivery_address"]).strip(" ,")
    header["delivery_address"] = re.sub(r"^הגורן\s*43\s*", "", header["delivery_address"]).strip(" ,")

    m = re.search(r"([0-9.,]+)\s+ח\"ש\s+([0-9.,]+)\s+'חי\s+([0-9.,]+)\s+'חי\s+[0-9.,]+\s+\d{2}/\d{2}/\d{2}\s+(.+?)\s+([0-9]{10})\s+\d+", text)
    item = POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="")
    if m:
        item = POItem(
            sku=m.group(5),
            description=m.group(4)[::-1].strip(),
            quantity=float(m.group(3).replace(",", "")),
            unit_price=float(m.group(2).replace(",", "")),
            line_total=float(m.group(1).replace(",", "")),
        )
        header["subtotal"] = item.line_total

    m = re.search(r"([0-9.,]+)\s+\(18\.00%\)\s+מ\"עמ", text)
    if m:
        header["vat"] = float(m.group(1).replace(",", ""))

    m = re.search(r"ח\"ש\s+([0-9.,]+)\s+ריחמ כ\"הס", text)
    if m:
        header["total"] = float(m.group(1).replace(",", ""))

    m = re.search(r"(\d+)ש\s*:\s*םולשת יאנת", text)
    if m:
        header["payment_terms_days"] = int(m.group(1))
        header["payment_terms_label"] = f"שוטף + {m.group(1)}"

    contact_name, contact_phone = sanitize_contact_pair(
        header.get("contact_name", ""),
        header.get("contact_phone", ""),
        customer_phone=header.get("customer_phone", ""),
    )
    header["contact_name"] = contact_name
    header["contact_phone"] = contact_phone

    return CUSTOMER_NAME, [item], header
