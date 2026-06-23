import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws, sanitize_contact_pair


CUSTOMER_NAME = 'ארטק טכנולוגיות כחול לבן בע"מ'


def _clean(value: str) -> str:
    return normalize_ws(re.sub(r"[\u200e\u200f\u202a-\u202e]", "", value or ""))


def _amount(value: str) -> float:
    token = normalize_ws(value or "").replace(",", "").replace("₪", "").replace('ש"ח', "")
    try:
        return float(token)
    except Exception:
        return 0.0


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return ""
    if digits.startswith("972") and len(digits) >= 11:
        digits = "0" + digits[3:]
    if len(digits) == 9 and digits.startswith(("3", "4", "5", "8")):
        digits = "0" + digits
    if len(digits) == 10:
        return f"{digits[:2]}-{digits[2:]}" if digits.startswith("0") and digits[1] in "23489" else f"{digits[:3]}-{digits[3:]}"
    return value


def _reverse_words(value: str) -> str:
    tokens = [token for token in normalize_ws(value or "").split(" ") if token]
    converted: list[str] = []
    for token in reversed(tokens):
        if re.search(r"[א-ת]", token):
            converted.append(token[::-1])
        else:
            converted.append(token)
    return normalize_ws(" ".join(converted))


def parse(text: str):
    if "קטרא" not in text and "ARTEK TECHNOLOGIES" not in text and "WWW.ARTEK-BAGS.COM" not in text:
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
    }

    id_match = re.search(r"\d{8}\s+ט\"בהשמ קפס\s+(\d{9})\s+\.פ\.ח", flat)
    if id_match:
        header["customer_id"] = id_match.group(1)[::-1]

    po_match = re.search(r"(\d{6})\s*:\s*שכר תנמזה", flat)
    if po_match:
        header["po_number"] = po_match.group(1)

    date_match = re.search(r"(\d{2}/\d{2}/\d{4})\s*:\s*ךיראת", flat)
    if date_match:
        header["po_date"] = normalize_date(date_match.group(1))

    footer_phone = re.search(r"Tel:\s*\+972-(\d)-(\d+)", flat, re.IGNORECASE)
    if footer_phone:
        header["customer_phone"] = _normalize_phone(f"0{footer_phone.group(1)}-{footer_phone.group(2)}")

    contact_match = re.search(r"(.+?)\s*:\s*ליעפ להנמ", flat)
    if contact_match:
        header["contact_name"] = _reverse_words(contact_match.group(1))

    direct_phone = re.search(r"(\d{2}-\d{7,8})\s*:\s*ופלט", flat)
    if direct_phone:
        header["contact_phone"] = _normalize_phone(direct_phone.group(1))

    item = POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="")
    item_match = re.search(
        r"\d{2}/\d{2}/\d{4}\s+([0-9,]+\.\d{2})\s+[0-9,]+\.\d{2}\s+ח\"ש\s+([0-9,]+\.\d{2})\s+([0-9,]+\.\d{2})\s+(.+?)\s+(\d{7})\s+0",
        flat,
    )
    if item_match:
        line_total = _amount(item_match.group(1))
        unit_price = _amount(item_match.group(2))
        quantity = _amount(item_match.group(3))
        description = _reverse_words(item_match.group(4))
        sku = item_match.group(5)[::-1]
        item = POItem(
            sku=sku,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
        )
        header["subtotal"] = line_total

    subtotal_match = re.search(r"([0-9,]+\.\d{2})\s*:\s*מ\"עמ ינפל כ\"הס", flat)
    if subtotal_match:
        header["subtotal"] = _amount(subtotal_match.group(1))

    vat_match = re.search(r"([0-9,]+\.\d{2})\s*:\s*עמ\"", flat)
    if vat_match:
        header["vat"] = _amount(vat_match.group(1))

    total_match = re.search(r"([0-9,]+\.\d{2})\s*:\s*םולשתל כ\"הס", flat)
    if total_match:
        header["total"] = _amount(total_match.group(1))

    contact_name, contact_phone = sanitize_contact_pair(
        header.get("contact_name", ""),
        header.get("contact_phone", ""),
        customer_phone=header.get("customer_phone", ""),
    )
    header["contact_name"] = contact_name
    header["contact_phone"] = contact_phone

    return CUSTOMER_NAME, [item], header
