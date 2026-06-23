import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_po_number, normalize_ws, sanitize_contact_pair


CUSTOMER_NAME = 'אלקטרה בניה בע"מ ואשטרום הנדסה ובניה בע"מ'


def _clean(value: str) -> str:
    return normalize_ws(re.sub(r"[\u200e\u200f\u202a-\u202e]", "", value or ""))


def _amount(value: str) -> float:
    token = normalize_ws(value or "").replace(",", "").replace("₪", "").replace('ש"ח', "").replace("חש", "")
    try:
        return float(token)
    except Exception:
        return 0.0


def _reverse_words(value: str) -> str:
    tokens = [token for token in normalize_ws(value or "").split(" ") if token]
    converted: list[str] = []
    for token in reversed(tokens):
        if re.search(r"[א-ת]", token):
            converted.append(token[::-1])
        else:
            converted.append(token)
    return normalize_ws(" ".join(converted))


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return ""
    if len(digits) == 9 and digits.startswith(("3", "4", "5", "8")):
        digits = "0" + digits
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:]}"
    return value


def parse(text: str):
    if "םורטשא" not in text and "kikar@electra.co.il" not in text:
        return None

    lines = [_clean(line) for line in text.splitlines() if _clean(line)]
    flat = "\n".join(lines)

    header = {
        "customer_id": "",
        "po_number": "",
        "po_date": "",
        "customer_phone": "",
        "delivery_address": "",
        "project": "",
        "contact_name": "",
        "contact_phone": "",
        "subtotal": 0.0,
        "vat": 0.0,
        "total": 0.0,
        "payment_terms_days": None,
        "payment_terms_label": "",
    }

    id_match = re.search(r"(\d{9})\s*:\s*השרומ קסוע", flat)
    if id_match:
        header["customer_id"] = id_match.group(1)

    po_match = re.search(r"(PO\d+)\s+רפסמ שכר תנמזה", flat)
    if po_match:
        header["po_number"] = normalize_po_number(po_match.group(1))

    date_match = re.search(r"(\d{2}/\d{2}/\d{2})\s*:\s*הנמזה ךיראת", flat)
    if date_match:
        header["po_date"] = normalize_date(date_match.group(1))

    phone_match = re.search(r"([0-9.\-]+)\s*:\s*סקפ\s*,\s*([0-9.\-]+)\s*:\s*ןופלט", flat)
    if phone_match:
        header["customer_phone"] = _normalize_phone(phone_match.group(2))

    project_match = re.search(r"(.+?)\s*:\s*טקיורפ להנמ", flat)
    if project_match:
        header["project"] = _reverse_words(project_match.group(1))

    address_parts: list[str] = []
    site_line_match = re.search(r"\n([^\n]*הרטקלא[^\n]*הנידמה רכיכ[^\n]*)\n", flat)
    if site_line_match:
        first = site_line_match.group(1).replace("34 ןרוגה", "").strip(" ,-")
        if first:
            address_parts.append(_reverse_words(first))
    street_line_match = re.search(r"\n([^\n]*ה['׳] באייר[^\n]*)\nביבא לת", flat)
    if street_line_match:
        second = re.sub(r".*054-7720142\s*:\s*ןופלט", "", street_line_match.group(1)).strip(" ,-")
        if second:
            address_parts.append(_reverse_words(second))
    if site_line_match or street_line_match:
        address_parts.append("תל אביב")
    header["delivery_address"] = normalize_ws(", ".join(part for part in address_parts if part))

    contact_match = re.search(r"(.+?)\s*:\s*ידיל", flat)
    if contact_match:
        header["contact_name"] = _reverse_words(contact_match.group(1))

    mobile_match = re.search(r"([0-9\-]+)\s*:\s*דיינ", flat)
    if mobile_match:
        header["contact_phone"] = _normalize_phone(mobile_match.group(1))

    item = POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="")
    item_match = re.search(
        r"([0-9,]+\.\d{2})\s+1\.00000\s+חש\s+([0-9,]+\.\d{2})\s+'חי\s+([0-9,]+\.\d{2})\s+(.*?)\s+(\d{12})\s+1",
        flat,
        re.DOTALL,
    )
    if item_match:
        desc = _reverse_words(item_match.group(4))
        desc = re.sub(r"\s+\d{2}/\d{2}/\d{2}$", "", desc).strip()
        item = POItem(
            sku=item_match.group(5),
            description=desc,
            quantity=_amount(item_match.group(3)),
            unit_price=_amount(item_match.group(2)),
            line_total=_amount(item_match.group(1)),
        )
        header["subtotal"] = item.line_total

    subtotal_match = re.search(r"([0-9,]+\.\d{2})\s+ללוכ ריחמ", flat)
    if subtotal_match:
        header["subtotal"] = _amount(subtotal_match.group(1))

    vat_match = re.search(r"([0-9,]+\.\d{2})\s+\(18\.00%\)\s+מ\"עמ", flat)
    if vat_match:
        header["vat"] = _amount(vat_match.group(1))

    total_match = re.search(r"חש\s+([0-9,]+\.\d{2})\s+ריחמ כ\"הס", flat)
    if total_match:
        header["total"] = _amount(total_match.group(1))

    terms_match = re.search(r"(\d+)\s*\+\s*ףטוש", flat)
    if terms_match:
        header["payment_terms_days"] = int(terms_match.group(1))
        header["payment_terms_label"] = f"שוטף + {terms_match.group(1)}"

    contact_name, contact_phone = sanitize_contact_pair(
        header.get("contact_name", ""),
        header.get("contact_phone", ""),
        customer_phone=header.get("customer_phone", ""),
    )
    header["contact_name"] = contact_name
    header["contact_phone"] = contact_phone

    return CUSTOMER_NAME, [item], header
