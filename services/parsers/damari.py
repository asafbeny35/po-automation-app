import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws, sanitize_contact_pair


CUSTOMER_NAME = 'י.ח. דמרי בניה ופיתוח בע"מ'


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
    if len(digits) == 9 and digits.startswith(("3", "4", "8", "9")):
        digits = "0" + digits
    if len(digits) == 10:
        return f"{digits[:2]}-{digits[2:]}" if digits[1] in "3489" else f"{digits[:3]}-{digits[3:]}"
    return normalize_ws(value or "")


def _extract_name_phone_from_reversed_line(value: str) -> tuple[str, str]:
    clean = normalize_ws(value or "")
    if not clean:
        return "", ""
    match = re.search(r"((?:972|0)?\d{8,9})", clean)
    if not match:
        return "", ""
    phone = _normalize_phone(match.group(1))
    name_part = normalize_ws((clean[:match.start()] + " " + clean[match.end():]).strip(" -:"))
    name = _reverse_words(name_part)
    return name, phone


def _reverse_words(value: str) -> str:
    tokens = [token for token in normalize_ws(value or "").split(" ") if token]
    converted: list[str] = []
    for token in reversed(tokens):
        if re.search(r"[א-ת]", token):
            converted.append(token[::-1])
        else:
            converted.append(token)
    return normalize_ws(" ".join(converted))


def _normalize_reversed_date(value: str) -> str:
    clean = normalize_ws(value or "")
    if not clean:
        return ""
    normalized = normalize_date(clean)
    if re.match(r"\d{2}/\d{2}/\d{4}$", normalized):
        return normalized
    parts = clean.split("/")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        day, month, year = parts
        return f"{day[::-1]}/{month[::-1]}/{year[::-1]}"
    return clean


def _extract_items(lines: list[str], flat: str) -> list[POItem]:
    items: list[POItem] = []
    line_pattern = re.compile(
        r"^([0-9,]+\.\d{2})\s+([0-9,]+\.\d{4})\s+([0-9,]+\.\d{2})\s+([0-9,]+\.\d{2})\s+(?:'חי|יח')\s+(.+?)\s+(\d{4,})$"
    )
    line_pattern_with_size = re.compile(
        r"^([0-9,]+\.\d{2})\s+([0-9,]+\.\d{4})\s+([0-9,]+\.\d{2})\s+(\d+(?:\.\d{1,2})?)\s+([0-9.]+\s*/\s*[0-9.]+)\s+(.+?)\s+(\d{4,})$"
    )

    for line in lines:
        if "כ\"הס ינפל" in line or "מ\"עמ" in line or "תורעה" in line:
            continue
        sized_match = line_pattern_with_size.match(line)
        if sized_match:
            line_total = _amount(sized_match.group(1))
            unit_price = _amount(sized_match.group(2))
            quantity = _amount(sized_match.group(4) or sized_match.group(3))
            size_token = normalize_ws(sized_match.group(5)).replace(" ", "")
            sku = sized_match.group(7)
            description_core = _reverse_words(sized_match.group(6)).replace(" -", " - ").strip()
            description = normalize_ws(f"{description_core} {size_token}".replace(" -מידות", " - מידות")).strip(" -,") or "פריט לא זוהה"
            items.append(
                POItem(
                    sku=sku,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                    unit="יח'",
                )
            )
            continue
        match = line_pattern.match(line)
        if not match:
            continue
        line_total = _amount(match.group(1))
        unit_price = _amount(match.group(2))
        quantity = _amount(match.group(4))
        sku = match.group(6)
        description = _reverse_words(match.group(5)).replace(" -", " - ").strip()
        description = normalize_ws(description).strip(" -,") or "פריט לא זוהה"
        items.append(
            POItem(
                sku=sku,
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
                unit="יח'",
            )
        )

    if items:
        return items

    fallback_match = re.search(
        r"([0-9,]+\.\d{2})\s+([0-9,]+\.\d{4})\s+([0-9,]+\.\d{2})\s+([0-9,]+\.\d{2})\s+'חי\s+(.+?)\s+(\d{4,})",
        flat,
    )
    if fallback_match:
        return [
            POItem(
                sku=fallback_match.group(6),
                description=_reverse_words(fallback_match.group(5)) or "פריט לא זוהה",
                quantity=_amount(fallback_match.group(4)),
                unit_price=_amount(fallback_match.group(2)),
                line_total=_amount(fallback_match.group(1)),
                unit="יח'",
            )
        ]

    return [POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="", unit="")]


def parse(text: str):
    if "ירמד .ח.י" not in text and "י.ח. דמרי" not in text and "י.ח. דמרי בניה ופיתוח" not in text:
        return None

    lines = [_clean(line) for line in text.splitlines() if _clean(line)]
    flat = "\n".join(lines)

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
        "extra": {},
    }

    id_match = re.search(r"(\d{9})\s+פ\.ח", flat)
    if id_match:
        header["customer_id"] = id_match.group(1)

    phone_match = re.search(r"(\d{2}-\d{7})\s*:\s*ןופלט", flat)
    if phone_match:
        header["customer_phone"] = _normalize_phone(phone_match.group(1))

    po_match = re.search(r"(\d+)\s+שכר תנמזה", flat)
    if po_match:
        header["po_number"] = po_match.group(1)

    date_match = re.search(r"(\d{2}/\d{2}/\d{4})\s*:\s*הנמזה ךיראת", flat)
    if date_match:
        header["po_date"] = _normalize_reversed_date(date_match.group(1))

    project_match = re.search(r"(.+?)\s*:\s*טקיורפ", flat)
    if project_match:
        header["project"] = _reverse_words(project_match.group(1))

    contact_line_match = re.search(r"([^\n]+)\s*:\s*רשק שיא", flat)
    if contact_line_match:
        raw_contact_line = contact_line_match.group(1)
        address_match = re.search(r":רוזיא\s+(.+?)\s*:תבותכ", raw_contact_line)
        if address_match:
            header["delivery_address"] = _reverse_words(address_match.group(1)).replace(" -", "-").strip()
        contact_name = raw_contact_line.split(":רוזיא", 1)[0].strip()
        header["contact_name"] = _reverse_words(contact_name)

    for index, line in enumerate(lines):
        if ":רשק שיא" not in line:
            continue
        previous_line = lines[index - 1] if index > 0 else ""
        if previous_line:
            extracted_name, extracted_phone = _extract_name_phone_from_reversed_line(previous_line)
            if extracted_name:
                header["contact_name"] = extracted_name
            elif not re.search(r"\d", previous_line):
                header["contact_name"] = _reverse_words(previous_line)
            if extracted_phone:
                header["contact_phone"] = extracted_phone
        break

    if not header["delivery_address"]:
        address_line_match = re.search(r":רוזיא\s+([^\n]+?)\s*:תבותכ", flat)
        if address_line_match:
            header["delivery_address"] = _reverse_words(address_line_match.group(1)).replace(" -", "-").strip()

    items = _extract_items(lines, flat)
    item = items[0] if items else POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="", unit="")

    subtotal_match = re.search(r"([0-9,]+\.\d{2})\s+מ\"עמו החנה ינפל כ\"הס", flat)
    if subtotal_match:
        header["subtotal"] = _amount(subtotal_match.group(1))
    else:
        header["subtotal"] = item.line_total

    vat_match = re.search(r"([0-9,]+\.\d{2})\s+00\.81\s+%\s+מ\"עמ", flat)
    if vat_match:
        header["vat"] = _amount(vat_match.group(1))

    total_match = re.search(r"([0-9,]+\.\d{2})\s+מ\"עמ ללוכ כ\"הס", flat)
    if total_match:
        header["total"] = _amount(total_match.group(1))

    request_match = re.search(r"(\d+)\s+שכר תשקב ס\"ע", flat)
    dimensions_match = re.search(r"([0-9.]+\*[0-9.]+)", flat)
    doors_match = re.search(r"([0-9/]+)\s+הנגה תותלד", flat)
    if request_match:
        header["extra"]["purchase_request_number"] = request_match.group(1)
    if dimensions_match:
        header["extra"]["dimensions"] = dimensions_match.group(1)
    if doors_match:
        header["extra"]["door_spec"] = f"דלתות הגנה {doors_match.group(1)}"

    if header["subtotal"] and header["total"] and not header["vat"]:
        header["vat"] = round(header["total"] - header["subtotal"], 2)

    contact_name, contact_phone = sanitize_contact_pair(
        header.get("contact_name", ""),
        header.get("contact_phone", ""),
        customer_phone=header.get("customer_phone", ""),
    )
    header["contact_name"] = contact_name
    header["contact_phone"] = contact_phone

    return CUSTOMER_NAME, items, header
