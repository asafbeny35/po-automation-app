import re

from services.models import POItem
from services.parsers.common import fix_hebrew_rtl_text, normalize_ws


CUSTOMER_NAME = 'לוינשטין נתיב הנדסה ובנין בע"מ'

_ITEM_LINE_PATTERN = re.compile(
    r"^1\s+(\d{8})\s+(.*?)\s+([0-9.,]+)\s+([^\s]+)\s+₪?([0-9.,]+)\s+([0-9.,]+)$"
)


def _normalize_text(text: str) -> str:
    raw = str(text or "")
    if "טקיורפ" in raw or "שרגמ" in raw or "שכר תנמזה" in raw:
        return fix_hebrew_rtl_text(raw)
    return raw


def _parse_amount(value: str) -> float:
    normalized = str(value or "").replace("₪", "").replace(",", "").strip()
    if not normalized:
        return 0.0
    try:
        return float(normalized)
    except Exception:
        return 0.0


def _extract_item_line(lines: list[str]) -> str:
    for line in lines:
        candidate = normalize_ws(line)
        if _ITEM_LINE_PATTERN.match(candidate):
            return candidate
    return ""


def _extract_description_and_numbers(item_line: str) -> tuple[str, float, float, float, str, str]:
    match = _ITEM_LINE_PATTERN.match(normalize_ws(item_line))
    if not match:
        return "פריט לא זוהה", 1.0, 0.0, 0.0, "", ""

    sku = match.group(1).strip()
    description = normalize_ws(match.group(2)).strip(" -")
    quantity = _parse_amount(match.group(3))
    unit = normalize_ws(match.group(4)).strip()
    unit_price = _parse_amount(match.group(5))
    line_total = _parse_amount(match.group(6))

    return description or "פריט לא זוהה", quantity, unit_price, line_total, sku, unit


def parse_levinstein(text: str):
    normalized_text = _normalize_text(text)
    lines = [normalize_ws(line).strip() for line in normalized_text.splitlines() if normalize_ws(line).strip()]
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

    tax_id_match = re.search(r"פ\.?ח[:\s]*([0-9]{9})", flat) or re.search(r"([0-9]{9})\s*:\s*פ\.?ח", flat)
    if tax_id_match:
        header["customer_id"] = tax_id_match.group(1).strip()

    email_match = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", flat)
    if email_match:
        header["customer_email"] = email_match.group(1).strip()

    po_match = re.search(r"הזמנת רכש מס[:\s]*([0-9]+)", flat)
    if po_match:
        header["po_number"] = po_match.group(1).strip()

    po_date_match = re.search(r"תאריך הזמנה[:\s]*([0-9/]+)", flat)
    if po_date_match:
        header["po_date"] = po_date_match.group(1).strip()

    customer_phone_match = re.search(r"טלפון[:\s]*([0-9\-]+)", flat)
    if customer_phone_match:
        header["customer_phone"] = customer_phone_match.group(1).strip()

    project_match = re.search(r"פרויקט[:\s]*([^\n]+)", flat)
    if project_match:
        project_value = project_match.group(1).strip()
        if "לידי:" in project_value:
            project_value = project_value.split("לידי:", 1)[0].strip()
        header["project"] = normalize_ws(project_value).strip(" -")

    delivery_match = re.search(r"כתובת פרויקט[:\s]*([^\n]+)", flat)
    if delivery_match:
        header["delivery_address"] = normalize_ws(delivery_match.group(1)).strip(" -")
    if not header["delivery_address"]:
        header["delivery_address"] = header["project"]

    contact_match = re.search(r"לידי[:\s]*([^,\n]+)\s*,\s*([0-9\-]+)", flat)
    if contact_match:
        header["contact_name"] = normalize_ws(contact_match.group(1)).strip()
        header["contact_phone"] = contact_match.group(2).strip()
    else:
        notes_contact_match = re.search(r"הערות למסמך[:\s]*[0-9]+\s+([^0-9\n]+)\s+([0-9]{10})", flat)
        if notes_contact_match:
            header["contact_name"] = normalize_ws(notes_contact_match.group(1)).strip()
            header["contact_phone"] = notes_contact_match.group(2).strip()

    subtotal_match = re.search(r"סה\"כ חייב במע\"מ[:\s]*([0-9.,]+)", flat)
    if subtotal_match:
        header["subtotal"] = _parse_amount(subtotal_match.group(1))

    vat_match = re.search(r"מע\"מ[:\s]*%\s*[0-9.,]+\s+([0-9.,]+)", flat)
    if vat_match:
        header["vat"] = _parse_amount(vat_match.group(1))

    total_match = re.search(r"סה\"כ מסמך[:\s]*([0-9.,]+)", flat)
    if total_match:
        header["total"] = _parse_amount(total_match.group(1))

    item_line = _extract_item_line(lines)
    description, quantity, unit_price, line_total, sku, unit = _extract_description_and_numbers(item_line)

    item = POItem(
        sku=sku,
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
        unit=unit,
    )

    return CUSTOMER_NAME, [item], header
