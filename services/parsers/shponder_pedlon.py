import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws, sanitize_contact_pair


CUSTOMER_NAME = 'פדלון שפונדר ביצוע בע"מ'
CUSTOMER_ID = "516087269"
REVERSED_CUSTOMER_NAME = 'מ"עב עוציב רדנופש ןולדפ'


def _clean(value: str) -> str:
    return normalize_ws(re.sub(r"[\u200e\u200f\u202a-\u202e]", "", value or ""))


def _normalized_text(text: str) -> str:
    cleaned = _clean(text)
    cleaned = cleaned.replace("|", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return ""
    if len(digits) == 8:
        digits = "0" + digits
    elif len(digits) == 9 and not digits.startswith("0"):
        digits = "0" + digits
    if len(digits) == 10:
        return f"{digits[:2]}-{digits[2:]}" if digits.startswith("09") else f"{digits[:3]}-{digits[3:]}"
    if len(digits) == 9 and digits.startswith("0"):
        return f"{digits[:2]}-{digits[2:]}" if digits.startswith("09") else f"{digits[:3]}-{digits[3:]}"
    return _clean(value)


def _amount(value: str) -> float:
    cleaned = _clean(value).replace(",", "").replace("₪", "").replace("%", "").replace('ש"ח', "")
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    try:
        return float(cleaned) if cleaned else 0.0
    except Exception:
        return 0.0


def _detect(text: str) -> bool:
    cleaned = _normalized_text(text)
    return (
        (CUSTOMER_NAME in cleaned or REVERSED_CUSTOMER_NAME in cleaned)
        and "הזמנת רכש" in cleaned
    )


def _build_lines(text: str) -> list[str]:
    return [_clean(line) for line in (text or "").splitlines() if _clean(line)]


def _extract_first(pattern: str, text: str, flags=re.MULTILINE) -> str:
    match = re.search(pattern, text, flags)
    return _clean(match.group(1)) if match else ""


def _extract_email(text: str) -> str:
    normalized = re.sub(r"\s+", "", _clean(text))
    match = re.search(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})", normalized, re.IGNORECASE)
    return match.group(1) if match else ""


def _normalize_description(value: str) -> str:
    description = normalize_ws(value).strip(" -")
    description = description.replace("DAV NIT NA", "המידות טרם")
    return normalize_ws(description)


def _extract_amount_near_label(lines: list[str], label: str) -> float:
    for index, line in enumerate(lines):
        if label not in line:
            continue
        inline_match = re.search(rf"{re.escape(label)}\s*:?\s*([0-9,]+\.\d{{2}})", line)
        if inline_match:
            return _amount(inline_match.group(1))

        candidates = lines[index:index + 6]
        for candidate in candidates:
            for number in re.findall(r"[0-9,]+\.\d{2}", candidate):
                return _amount(number)
    return 0.0


def _extract_vat_details(lines: list[str]) -> tuple[float, float]:
    for index, line in enumerate(lines):
        if 'מע"מ:' not in line or 'חייב במע"מ' in line:
            continue
        numbers: list[float] = []
        for candidate in lines[index:index + 5]:
            numbers.extend(_amount(number) for number in re.findall(r"[0-9,]+\.\d{2}", candidate))
        if not numbers:
            continue
        rate_index = next((i for i, value in enumerate(numbers) if 0 <= value <= 100), -1)
        if rate_index != -1 and rate_index + 1 < len(numbers):
            return numbers[rate_index], numbers[rate_index + 1]
        if rate_index != -1:
            return numbers[rate_index], 0.0
        if len(numbers) >= 2:
            return 0.0, numbers[1]
        return 0.0, numbers[0]
    return 0.0, 0.0


def _extract_row_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    in_items = False

    for line in lines:
        if line.startswith("קוד פריט"):
            in_items = True
            continue
        if not in_items:
            continue
        if line.startswith("תנאי תשלום"):
            if current:
                blocks.append(current)
            break
        if re.fullmatch(r"\d+", line) or re.match(r"^\d+\s+[\d-]+\s+", line):
            if current and len(current) > 1:
                blocks.append(current)
            current = [line]
            continue
        if current:
            current.append(line)

    if current and current not in blocks:
        blocks.append(current)
    return blocks


def _parse_row(block: list[str]) -> POItem | None:
    inline_match = re.match(
        r"^\d+\s+([\d-]+)\s+(.+?)\s+(\d+(?:\.\d+)?)\s+(יח'?|יח|מ\"ר|מ2|מטר)\s+(\d{2}/\d{2}/\d{4})\s+₪?([0-9,]+\.\d{2})\s+([0-9,]+\.\d{2})$",
        block[0] if block else "",
    )
    if inline_match:
        description_parts = [_clean(inline_match.group(2))]
        description_parts.extend(_clean(line) for line in block[1:] if _clean(line))
        unit = _clean(inline_match.group(4))
        if unit == "יח":
            unit = "יח'"
        return POItem(
            sku=_clean(inline_match.group(1)),
            description=_normalize_description(" ".join(description_parts)) or "פריט לא זוהה",
            quantity=_amount(inline_match.group(3)),
            unit_price=_amount(inline_match.group(6)),
            line_total=_amount(inline_match.group(7)),
            unit=unit,
        )

    if len(block) < 7:
        return None

    row_number = block[0]
    if not re.fullmatch(r"\d+", row_number):
        return None

    sku = block[1] if re.fullmatch(r"[\d-]+", block[1]) else ""

    quantity_index = next(
        (
            index
            for index, value in enumerate(block[2:], start=2)
            if re.fullmatch(r"\d+(?:\.\d+)?", value)
        ),
        -1,
    )
    if quantity_index == -1:
        return None

    unit_index = quantity_index + 1 if quantity_index + 1 < len(block) else -1
    date_index = quantity_index + 2 if quantity_index + 2 < len(block) else -1
    unit_price_index = quantity_index + 3 if quantity_index + 3 < len(block) else -1
    line_total_index = quantity_index + 4 if quantity_index + 4 < len(block) else -1

    if min(unit_index, date_index, unit_price_index, line_total_index) == -1:
        return None

    description_lines = [line for line in block[2:quantity_index] if line]
    description = _normalize_description(" ".join(description_lines)) or "פריט לא זוהה"

    return POItem(
        sku=sku,
        description=description,
        quantity=_amount(block[quantity_index]),
        unit_price=_amount(block[unit_price_index]),
        line_total=_amount(block[line_total_index]),
        unit=_clean(block[unit_index]),
    )


def parse(text: str):
    raw_text = str(text or "")
    if not _detect(raw_text):
        return None

    lines = _build_lines(raw_text)
    flat = "\n".join(lines)

    customer_phone = ""
    phone_matches = re.findall(r"0\d{1,2}-\d{7}", flat)
    if phone_matches:
        customer_phone = _normalize_phone(phone_matches[0])

    po_number = _extract_first(r"הזמנת רכש\s*(?:מ0?ס|מס)?\s*:?\s*([A-Za-z0-9/-]+)", flat)
    po_date = normalize_date(_extract_first(r"תאריך הזמנה\s*:?\s*([0-9]{2}/[0-9]{2}/[0-9]{4})", flat))
    project = _extract_first(r"פרויקט\s*:?\s*([^\n|]+)", flat)
    if " לידי:" in project:
        project = project.split(" לידי:", 1)[0].strip()
    delivery_address = _extract_first(r"כתובת פרויקט\s*:?\s*([^\n]+)", flat)
    delivery_address = delivery_address.lstrip("| ").strip()

    contact_name = ""
    contact_phone = ""
    contact_match = re.search(r"לידי\s*:?\s*[|]?\s*([א-ת\"'׳\-\s]+?)[,\s]+(0\d{1,2}-\d{7})", flat)
    if contact_match:
        contact_name = _clean(contact_match.group(1))
        contact_phone = _normalize_phone(contact_match.group(2))

    contact_name, contact_phone = sanitize_contact_pair(
        contact_name,
        contact_phone,
        customer_phone=customer_phone,
    )

    customer_email = _extract_email(flat)
    accounting_contact_name = ""
    accounting_match = re.search(r"בכבוד רב\s*:?\s*([א-ת\"'׳\-\s]+)", flat)
    if accounting_match:
        accounting_contact_name = _clean(accounting_match.group(1))
    if not accounting_contact_name:
        for index, line in enumerate(lines):
            if "בכבוד רב" in line and index + 1 < len(lines):
                accounting_contact_name = _clean(lines[index + 1])
                break

    payment_days = None
    payment_match = re.search(r"תנאי תשלום\s*:?\s*[|]?\s*שוטף\s*\+?\s*([0-9]+)\+?", flat)
    if payment_match:
        payment_days = int(payment_match.group(1))
    payment_label = f"שוטף + {payment_days}" if payment_days is not None else ""

    order_notes_parts: list[str] = []
    notes_line = _extract_first(r"הערות למסמך\s*:?\s*([^\n]+)", flat)
    if notes_line:
        order_notes_parts.append(notes_line)
    approval_line = next((line for line in lines if line.startswith("אושר")), "")
    if approval_line:
        order_notes_parts.append(approval_line)

    subtotal = _extract_amount_near_label(lines, 'סה"כ חייב במע"מ')
    if not subtotal:
        subtotal = _extract_amount_near_label(lines, 'סה"כ חייב במע"מ:')
    vat_rate, vat = _extract_vat_details(lines)
    total = _extract_amount_near_label(lines, 'סה"כ מסמך:')
    if not vat and subtotal and total:
        vat = round(total - subtotal, 2)
    if not vat_rate and subtotal and vat:
        vat_rate = round((vat / subtotal) * 100, 2)

    items = [item for item in (_parse_row(block) for block in _extract_row_blocks(lines)) if item]
    if not items:
        items = [POItem(description="פריט לא זוהה", quantity=1, unit_price=0.0, line_total=0.0, sku="", unit="")]

    header = {
        "customer_name": CUSTOMER_NAME,
        "customer_id": CUSTOMER_ID,
        "customer_phone": customer_phone,
        "customer_email": customer_email,
        "delivery_address": delivery_address,
        "po_number": po_number,
        "po_date": po_date,
        "subtotal": subtotal,
        "vat": vat,
        "total": total,
        "payment_terms_days": payment_days,
        "payment_terms_label": payment_label,
        "project": project,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "extra": {
            "vat_rate": vat_rate,
            "order_notes": " | ".join(part for part in order_notes_parts if part),
            "accounting_contact_name": accounting_contact_name,
            "accounting_contact_email": customer_email,
        },
    }

    return CUSTOMER_NAME, items, header
