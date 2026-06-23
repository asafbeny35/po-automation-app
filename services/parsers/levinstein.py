import re

from services.models import POItem


CUSTOMER_NAME = 'לוינשטין נתיב הנדסה ובנין בע"מ'


def _rev(value: str) -> str:
    return (value or "").strip()[::-1]


def _rev_amount(value: str) -> float:
    value = (value or "").strip().replace("₪", "")
    if not value:
        return 0.0
    return float(_rev(value).replace(",", ""))


def _rev_date(value: str) -> str:
    return _rev(value)


def _extract_item_line(lines: list[str]) -> str:
    for line in lines:
        if re.match(r"^1\s+\d{8}\s+", line):
            return line
    return ""


def _extract_description_and_numbers(item_line: str) -> tuple[str, float, float, float, str]:
    sku_match = re.match(r"^1\s+(\d{8})\s+(.*)$", item_line)
    if not sku_match:
        return "פריט לא זוהה", 1.0, 0.0, 0.0, ""

    raw_sku = sku_match.group(1)
    remainder = sku_match.group(2)
    sku = _rev(raw_sku)

    parts = remainder.split()
    qty_index = None
    for index in range(len(parts) - 1):
        if re.fullmatch(r"[0-9.]+", parts[index]) and parts[index + 1] in ('מ"ר', "יח'"):
            qty_index = index
            break

    if qty_index is None:
        return "פריט לא זוהה", 1.0, 0.0, 0.0, sku

    description = " ".join(parts[:qty_index]).strip()
    quantity = _rev_amount(parts[qty_index])
    unit_price = _rev_amount(parts[qty_index + 2]) if qty_index + 2 < len(parts) else 0.0
    line_total = _rev_amount(parts[qty_index + 3]) if qty_index + 3 < len(parts) else 0.0

    description = description.replace("(epiPteiuQ (", "QuietPipe ").replace(") -", "").strip()
    description = " ".join(description.split())

    return description, quantity, unit_price, line_total, sku


def parse_levinstein(text: str):
    print("👉 ENTERED LEVINSTEIN")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    flat = "\n".join(lines)

    header = {
        "customer_email": "",
        "customer_id": "",
        "po_number": "",
        "po_date": "",
        "subtotal": None,
        "vat": None,
        "total": None,
        "payment_terms_days": None,
        "payment_terms_label": "",
        "project": "",
        "delivery_address": "",
        "contact_name": "",
        "contact_phone": "",
        "customer_phone": "",
    }

    m = re.search(r"פ\.ח[:\s]*([0-9]{9})", flat) or re.search(r"([0-9]{9})\s*:\s*פ\.ח", flat)
    if m:
        header["customer_id"] = m.group(1)

    m = re.search(r",מייל:([^\s]+)", flat)
    if m:
        header["customer_email"] = _rev(m.group(1))

    m = re.search(r"הזמנת רכש מס[:\s]*([0-9]+)", flat)
    if m:
        header["po_number"] = _rev(m.group(1))

    m = re.search(r"תאריך הזמנה[:\s]*([0-9/]+)", flat)
    if m:
        header["po_date"] = _rev_date(m.group(1))

    phone_matches = re.findall(r"טלפון:\s*([0-9\-]+)", flat)
    if phone_matches:
        header["customer_phone"] = _rev(phone_matches[0])

    project_line = next((line for line in lines if line.startswith("פרויקט:")), "")
    if project_line:
        project_value = project_line.split("פרויקט:", 1)[1].strip()
        if "לידי:" in project_value:
            project_value = project_value.split("לידי:", 1)[0].strip()
        header["project"] = project_value

    m = re.search(r"כתובת פרויקט:\s*([^\n]+)", flat)
    if m:
        candidate = m.group(1).strip()
        if candidate and "קוד פריט" not in candidate:
            header["delivery_address"] = candidate
    if not header["delivery_address"]:
        header["delivery_address"] = header["project"]

    contact_match = re.search(r"לידי:\s*([^,\n]+),\s*([0-9\-]+)", project_line)
    if contact_match:
        header["contact_name"] = contact_match.group(1).strip()
        header["contact_phone"] = _rev(contact_match.group(2))
    else:
        m = re.search(r"הערות למסמך:\s*[0-9]+\s+([^0-9\n]+)\s+([0-9]{10})", flat)
        if m:
            header["contact_name"] = m.group(1).strip()
            header["contact_phone"] = _rev(m.group(2))

    m = re.search(r"סה\"כ חייב במע\"מ:\s*([0-9.,]+)", flat)
    if m:
        header["subtotal"] = _rev_amount(m.group(1))

    m = re.search(r"מע\"מ:\s*%\s*[0-9.]+\s*([0-9.,]+)", flat)
    if m:
        header["vat"] = _rev_amount(m.group(1))

    m = re.search(r"סה\"כ מסמך:\s*([0-9.,]+)", flat)
    if m:
        header["total"] = _rev_amount(m.group(1))

    item_line = _extract_item_line(lines)
    description, quantity, unit_price, line_total, sku = _extract_description_and_numbers(item_line)

    item = POItem(
        sku=sku,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
    )

    return CUSTOMER_NAME, [item], header
