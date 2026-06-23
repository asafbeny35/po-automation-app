import re

from services.models import POItem
from services.parsers.common import fix_hebrew_text, sanitize_contact_pair


CUSTOMER_NAME = 'טובול חומרי בניין בע"מ'


def _parse_amount(value: str) -> float:
    cleaned = re.sub(r"[^\d.,-]", "", str(value or "").strip()).replace(",", "")
    return float(cleaned) if cleaned else 0.0


def _normalize_date(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parts = raw.split("/")
    if len(parts) != 3:
        return raw
    day, month, year = parts
    if len(year) == 2:
        year = f"20{year}"
    return f"{day.zfill(2)}/{month.zfill(2)}/{year}"


def _extract_block(text: str, start_marker: str, end_marker: str) -> str:
    pattern = re.escape(start_marker) + r"(.*?)" + re.escape(end_marker)
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else ""


def _extract_customer_email(text: str) -> str:
    lines = [line.strip() for line in str(text or "").splitlines()]
    for index, line in enumerate(lines):
        if "@" not in line:
            continue
        candidate = line
        if "." not in line and index + 1 < len(lines):
            candidate = f"{line}{lines[index + 1]}"
        candidate = candidate.replace(" ", "").replace("\u202a", "").replace("\u202c", "")
        candidate = candidate.replace("\n", "")
        email_match = re.search(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", candidate, re.IGNORECASE)
        if email_match:
            extracted = email_match.group(1)
            if extracted.upper() == "OFFICE@BEN-YACOV.COM":
                continue
            return extracted
    return ""


def parse(text: str):
    raw_text = str(text or "")
    if not any(marker in raw_text for marker in ('שכר תנמזה', 'מרלו"ג מודיעין', "מרכז עינב", "הקפסא ןסחמל", "ןיעידומ :ןסחמל הקפסא")):
        return None

    header = {
        "customer_email": "",
        "customer_id": "",
        "po_number": "",
        "po_date": "",
        "subtotal": 0.0,
        "vat": 0.0,
        "total": 0.0,
        "payment_terms_days": 120,
        "payment_terms_label": "שוטף + 120",
        "project": "",
        "delivery_address": "",
        "contact_name": "",
        "contact_phone": "",
        "customer_phone": "",
    }

    po_match = re.search(r"^(\d+)\s+שכר תנמזה", raw_text, re.MULTILINE)
    if po_match:
        header["po_number"] = po_match.group(1).strip()

    customer_id_match = re.search(r"([0-9]{9})\s+:\.מ\.ע רפסמ", raw_text)
    if customer_id_match:
        header["customer_id"] = customer_id_match.group(1).strip()

    date_match = re.search(r"([0-9]{2}/[0-9]{2}/[0-9]{2,4})\s*:ךיראת", raw_text)
    if date_match:
        header["po_date"] = _normalize_date(date_match.group(1))

    delivery_match = re.search(r"([^\n]+)\s+:\ןסחמל הקפסא", raw_text)
    if delivery_match:
        header["delivery_address"] = fix_hebrew_text(delivery_match.group(1).strip())

    subtotal_match = re.search(r"([0-9,]+\.\d{2})\s+החנה ירחא כ\"הס", raw_text)
    if subtotal_match:
        header["subtotal"] = _parse_amount(subtotal_match.group(1))
    else:
        subtotal_match = re.search(r"([0-9,]+\.\d{2})\s+כ\"הס\s+:קפסל תועדוה", raw_text)
        if subtotal_match:
            header["subtotal"] = _parse_amount(subtotal_match.group(1))

    vat_match = re.search(r"([0-9,]+\.\d{2})\s+18\.0000\s+%\s+מ\"עמ", raw_text)
    if vat_match:
        header["vat"] = _parse_amount(vat_match.group(1))

    total_match = re.search(r"([0-9,]+\.\d{2})\s+םולשתל כ\"הס", raw_text)
    if total_match:
        header["total"] = _parse_amount(total_match.group(1))

    item = POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="")
    lines = [line.strip() for line in raw_text.splitlines()]
    producer_match = re.search(r"([^\n]+)\s*:קיפמ", raw_text)
    if producer_match:
        header["contact_name"] = fix_hebrew_text(producer_match.group(1).strip())

    mobile_values = re.findall(r"05\d-\d{7}", raw_text)
    if len(mobile_values) >= 2:
        header["contact_phone"] = mobile_values[0]
    elif mobile_values:
        header["contact_phone"] = mobile_values[0]

    header["customer_email"] = _extract_customer_email(raw_text)

    item_line_index = next(
        (index for index, line in enumerate(lines) if re.search(r"\d{9}\s+\d{9}\s+\d+$", line)),
        -1,
    )
    if item_line_index >= 0:
        item_line = lines[item_line_index]
        tokens = item_line.split()
        sku = tokens[-2] if len(tokens) >= 2 and re.fullmatch(r"\d{9}", tokens[-2]) else ""
        row_desc = tokens[-4] if len(tokens) >= 4 else ""
        quantity = float(tokens[-5]) if len(tokens) >= 5 and re.fullmatch(r"\d+(?:\.\d+)?", tokens[-5]) else 1.0
        unit_price = _parse_amount(tokens[0]) if tokens else 0.0
        description_parts = []
        for candidate_index in range(max(0, item_line_index - 2), min(len(lines), item_line_index + 3)):
            candidate = lines[candidate_index].strip()
            if not candidate or candidate == item_line:
                continue
            if candidate in {"הדימ", "'חי"}:
                continue
            if re.fullmatch(r"[0-9,.\-:/ ]+", candidate):
                continue
            description_parts.append(fix_hebrew_text(candidate).strip())
        if row_desc:
            description_parts.append(fix_hebrew_text(row_desc).strip())
        description = " ".join(part for part in description_parts if part).strip()
        description = re.sub(r"\s+", " ", description)
        description = description.replace("-)", "(").replace(" )", ")").replace(" (", " (").strip()
        description = description.replace("(גליל 2 מר(", "(גליל 2 מר)")
        line_total = header["subtotal"] or round(quantity * unit_price, 2)
        item = POItem(
            sku=sku,
            description=description or "פריט לא זוהה",
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
            unit="מר",
        )

    contact_name, contact_phone = sanitize_contact_pair(
        header["contact_name"],
        header["contact_phone"],
        customer_phone=header["customer_phone"],
    )
    header["contact_name"] = contact_name
    header["contact_phone"] = contact_phone

    return CUSTOMER_NAME, [item], header
