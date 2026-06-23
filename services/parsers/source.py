import re

from services.models import POItem
from services.parsers.common import normalize_amount, normalize_date, normalize_ws, sanitize_contact_pair


CUSTOMER_NAME = 'שורש טקטיקל גיר בע"מ'


def _reverse_hebrew_chunk(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return normalize_ws(text[::-1])


def _looks_like_item_line(line: str) -> bool:
    raw = str(line or "").strip()
    return bool(
        raw
        and "POG" not in raw
        and "*" in raw
        and re.search(r"\d{2}/\d{2}/\d{2}", raw)
        and re.search(r"\d+\.\d{2,3}", raw)
        and re.search(r"\b[A-Z0-9]+\b", raw)
    )


def _parse_item_line(raw_line: str) -> POItem | None:
    tokens = [token.strip() for token in str(raw_line or "").split() if token.strip()]
    if len(tokens) < 12:
        return None

    numeric_tokens = [token for token in tokens if re.fullmatch(r"[\d,]+\.\d{2,3}", token)]
    if len(numeric_tokens) < 3:
        return None

    star_code_index = next((idx for idx, token in enumerate(tokens) if re.fullmatch(r"\*[A-Z0-9]+\*", token)), -1)
    sku = ""
    if star_code_index >= 0 and star_code_index + 1 < len(tokens) and re.fullmatch(r"[A-Z0-9]+", tokens[star_code_index + 1]):
        sku = tokens[star_code_index + 1]
    else:
        sku_candidates = [token for token in tokens if re.fullmatch(r"[A-Z][A-Z0-9]+", token)]
        if sku_candidates:
            sku = sku_candidates[-1]
    if not sku:
        return None

    line_total = normalize_amount(tokens[0]) or 0.0
    unit_price = normalize_amount(tokens[2]) or 0.0
    quantity = normalize_amount(tokens[4]) or 0.0

    date_index = next((idx for idx, token in enumerate(tokens) if re.fullmatch(r"\d{2}/\d{2}/\d{2}", token)), -1)
    sku_index = star_code_index if star_code_index >= 0 else next((idx for idx in range(len(tokens) - 1, -1, -1) if tokens[idx] == sku), -1)
    if date_index == -1 or sku_index == -1 or sku_index <= date_index:
        return None

    description_tokens = tokens[date_index + 1:sku_index]
    description_parts = []
    for token in reversed(description_tokens):
        if re.search(r"[א-ת]", token):
            description_parts.append(token[::-1])
        else:
            description_parts.append(token)
    description = normalize_ws(" ".join(description_parts))
    description = re.sub(r"^\*?[A-Z0-9]+\*?\s*", "", description).strip()

    return POItem(
        sku=sku,
        description=description or "פריט לא זוהה",
        quantity=quantity or 1.0,
        unit_price=unit_price,
        line_total=line_total,
        unit='מ"ר',
    )


def parse(text: str):
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    flat = "\n".join(lines)

    if "שורש טקטיקל גיר" not in flat and "POG" not in flat and "sourcetacticalgear" not in flat.lower():
        return None

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

    po_match = re.search(r"\bPOG\d+\b", flat)
    if po_match:
        header["po_number"] = po_match.group(0)

    date_match = re.search(r"(\d{2}/\d{2}/\d{2})\s*:הנמזה ךיראת", flat)
    if date_match:
        header["po_date"] = normalize_date(date_match.group(1))

    customer_id_match = re.search(r"(\d{9})\s*:מ\"עמב קית רפסמ", flat)
    if customer_id_match:
        header["customer_id"] = customer_id_match.group(1)
    else:
        customer_id_match = re.search(r"(\d{9})\s*:השרומ קסוע", flat)
        if customer_id_match:
            header["customer_id"] = customer_id_match.group(1)

    email_match = re.search(r"e-?mail:\s*([^\s]+@[^\s]+)", flat, re.IGNORECASE)
    if email_match:
        header["customer_email"] = email_match.group(1).strip()

    phone_match = re.search(r"([0-9-]{9,})\s*:ןופלט", flat)
    if phone_match:
        header["customer_phone"] = phone_match.group(1).strip()

    fax_or_alt_phone_match = re.search(r"([0-9-]{9,})\s*:סקפ", flat)
    if fax_or_alt_phone_match and not header["contact_phone"]:
        header["contact_phone"] = fax_or_alt_phone_match.group(1).strip()

    details_match = re.search(r"([A-Z0-9]+)\s*:םיטרפ", flat)
    if details_match:
        header["project"] = details_match.group(1).strip()

    thanks_index = next((idx for idx, line in enumerate(lines) if line == ",הכרבב"), -1)
    if thanks_index != -1 and thanks_index + 1 < len(lines):
        header["contact_name"] = _reverse_hebrew_chunk(lines[thanks_index + 1])

    supplier_line_index = next((idx for idx, line in enumerate(lines) if "בקעי ןב" in line and "הספדה ךיראת" in line), -1)
    if supplier_line_index != -1:
        address_lines = []
        for candidate in lines[supplier_line_index + 1:]:
            if ":השרומ קסוע .סמ" in candidate or "רפסמ שכר תנמזה" in candidate:
                break
            address_lines.append(_reverse_hebrew_chunk(candidate))
            if len(address_lines) == 3:
                break
        header["delivery_address"] = normalize_ws(" | ".join(part for part in address_lines if part))

    subtotal_match = re.search(r"([\d,]+\.\d{2})\s+ללוכ ריחמ", flat)
    if subtotal_match:
        header["subtotal"] = normalize_amount(subtotal_match.group(1))

    vat_match = re.search(r"([\d,]+\.\d{2})\s+\)\%\d+\.\d+\(\s+מ\"עמ", flat)
    if vat_match:
        header["vat"] = normalize_amount(vat_match.group(1))

    total_match = re.search(r"ח'?ש\s*([\d,]+\.\d{2})\s+ריחמ כ\"הס", flat)
    if total_match:
        header["total"] = normalize_amount(total_match.group(1))

    payment_match = re.search(r"(\d+)\s*ש\s*:םולשת יאנת", flat)
    if payment_match:
        header["payment_terms_days"] = int(payment_match.group(1))
        header["payment_terms_label"] = f"שוטף + {header['payment_terms_days']}"

    if header["subtotal"] is None and header["total"] is not None and header["vat"] is not None:
        header["subtotal"] = round(float(header["total"]) - float(header["vat"]), 2)
    if header["total"] is None and header["subtotal"] is not None and header["vat"] is not None:
        header["total"] = round(float(header["subtotal"]) + float(header["vat"]), 2)
    if header["vat"] is None and header["subtotal"] is not None and header["total"] is not None:
        header["vat"] = round(float(header["total"]) - float(header["subtotal"]), 2)

    items = []
    for line in lines:
        if not _looks_like_item_line(line):
            continue
        item = _parse_item_line(line)
        if item:
            items.append(item)

    if not items:
        items = [POItem(description="פריט לא זוהה", quantity=1.0, unit_price=0.0, line_total=0.0, sku="")]

    contact_name, contact_phone = sanitize_contact_pair(
        header.get("contact_name", ""),
        header.get("contact_phone", ""),
        customer_phone=header.get("customer_phone", ""),
    )
    header["contact_name"] = contact_name
    header["contact_phone"] = contact_phone

    return CUSTOMER_NAME, items, header
