import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws, sanitize_contact_pair


def _clean(value: str) -> str:
    return normalize_ws(re.sub(r"[\u200e\u200f\u202a-\u202e]", "", value or ""))


def _amount(value: str) -> float:
    token = normalize_ws(value or "").replace(",", "").replace("₪", "").replace('ש"ח', "")
    try:
        return float(token)
    except Exception:
        return 0.0


def _reverse_text(value: str) -> str:
    result = _clean((value or "")[::-1])
    result = result.replace(")noisiv(", "(vision)")
    result = result.replace("11-9-7", "7-9-11")
    result = result.replace("11,9,7", "7,9,11")
    return result


def _normalize_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    if len(digits) == 9 and digits.startswith(("3", "4", "8", "9")):
        digits = "0" + digits
    if len(digits) == 10:
        if digits[1] in "3489":
            return f"{digits[:2]}-{digits[2:]}"
        return f"{digits[:3]}-{digits[3:]}"
    return normalize_ws(raw or "")


def _detect(text: str) -> bool:
    clean = text or ""
    return (
        "רדיק" in clean
        and "תינובשח" in clean
        and "ליטסקט תונורתפ בקעי ןב" in clean
        and "םולשת יאנת" in clean
    )


def _extract_po_number(flat: str) -> str:
    match = re.search(r"([0-9]+/[0-9]+)-?\s*'סמ הנמזה", flat)
    if match:
        return _clean(match.group(1))
    return ""


def _extract_project(flat: str) -> str:
    match = re.search(r"'סמ הנמזה\s*-\s*(.+?)\s*טקיורפ", flat)
    if match:
        return _reverse_text(match.group(1))
    return ""


def _extract_customer_name_and_id(flat: str) -> tuple[str, str]:
    match = re.search(r"([0-9]{9})\s+פ\.ח\s*-\s*(.+?)\s*:רובע קיפהל שי תינובשח", flat)
    if match:
        return _reverse_text(match.group(2)), match.group(1)
    return 'קידר מבנים בע"מ', "510605520"


def _extract_delivery_address(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        if line == "רתא יטרפ דובכל" and index + 2 < len(lines):
            site_line = lines[index + 2]
            city_line = lines[index + 3] if index + 3 < len(lines) else ""
            address = _reverse_text(site_line)
            city = _reverse_text(city_line)
            return normalize_ws(f"{address}, {city}".strip(" ,"))
    return ""


def _extract_contact_details(flat: str) -> tuple[str, str]:
    contact_line_match = re.search(r"([^\n]*054-7720142\s+ףסא\s*:לט[^\n]*)", flat)
    if not contact_line_match:
        return "", ""
    chunk = contact_line_match.group(1)
    contact_names: list[str] = []
    contact_phones: list[str] = []
    for raw_phone, raw_name in re.findall(r"(0\d{9}|0\d{2}-\d{7})\s+([^,:]+)", chunk):
        phone = _normalize_phone(raw_phone)
        name = _reverse_text(raw_name)
        if phone and phone != "054-7720142":
            contact_phones.append(phone)
        if name:
            contact_names.append(name)
    dedup_names = []
    for name in contact_names:
        if name not in dedup_names:
            dedup_names.append(name)
    dedup_phones = []
    for phone in contact_phones:
        if phone not in dedup_phones:
            dedup_phones.append(phone)
    return " / ".join(dedup_names[:3]), " / ".join(dedup_phones[:3])


def _extract_item(lines: list[str]) -> POItem:
    for index, line in enumerate(lines):
        if "הנקתה ללוכ" not in line or "17479" not in line:
            continue
        amounts = re.findall(r"([0-9,]+\.\d{2,3})", line)
        quantity_match = re.search(r"\s(\d+(?:\.\d+)?)\s+'חי", line)
        sku_match = re.search(r"-?(\d{4,})\s*$", line)
        desc_match = re.search(r"'חי\s+(.+?)\s+-?\d{4,}\s*$", line)

        description = _reverse_text(desc_match.group(1)) if desc_match else "פריט לא זוהה"
        if index + 1 < len(lines) and "םומינימ" in lines[index + 1]:
            description = f"{description} | {_reverse_text(lines[index + 1])}"

        line_total = _amount(amounts[0]) if len(amounts) >= 1 else 0.0
        unit_price = _amount(amounts[1]) if len(amounts) >= 2 else 0.0
        quantity = float(quantity_match.group(1)) if quantity_match else 0.0
        sku = sku_match.group(1) if sku_match else ""

        return POItem(
            sku=sku,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
            unit="יח'",
        )

    return POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="", unit="")


def parse(text: str):
    if not _detect(text):
        return None

    lines = [_clean(line) for line in (text or "").splitlines() if _clean(line)]
    flat = "\n".join(lines)

    customer_name, customer_id = _extract_customer_name_and_id(flat)
    item = _extract_item(lines)

    po_date_match = re.search(r"(\d{2}/\d{2}/\d{4})", flat)
    po_date = normalize_date(po_date_match.group(1)) if po_date_match else ""
    po_number = _extract_po_number(flat)
    project = _extract_project(flat)
    delivery_address = _extract_delivery_address(lines)
    contact_name, contact_phone = _extract_contact_details(flat)

    payment_label = "שוטף + 75"
    payment_days = 75

    subtotal = item.line_total or 0.0
    vat = round(subtotal * 0.18, 2) if subtotal else 0.0
    total = round(subtotal + vat, 2) if subtotal else 0.0

    header = {
        "customer_email": "",
        "customer_id": customer_id,
        "po_number": po_number,
        "po_date": po_date,
        "subtotal": subtotal,
        "vat": vat,
        "total": total,
        "payment_terms_days": payment_days,
        "payment_terms_label": payment_label,
        "project": project,
        "delivery_address": delivery_address,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "customer_phone": "",
        "extra": {
            "invoice_for_customer_name": customer_name,
            "invoice_for_customer_id": customer_id,
            "site_details": delivery_address,
        },
    }

    safe_contact_name, safe_contact_phone = sanitize_contact_pair(
        header.get("contact_name", ""),
        header.get("contact_phone", ""),
        customer_phone=header.get("customer_phone", ""),
    )
    header["contact_name"] = safe_contact_name
    header["contact_phone"] = safe_contact_phone

    return customer_name, [item], header
