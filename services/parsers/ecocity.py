import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws, sanitize_contact_pair


CUSTOMER_NAME = 'אקוסיטי אס אל הנדסה ובניה בע"מ'
CUSTOMER_ID = "513921668"


def _clean(value: str) -> str:
    return normalize_ws(re.sub(r"[\u200e\u200f\u202a-\u202e]", "", value or ""))


def _reverse_text(value: str) -> str:
    # PDF extractors keep digit runs in logical (LTR) order even inside RTL text.
    # Reversing the full string therefore reverses numbers — fix them back.
    reversed_str = _clean((value or "")[::-1])
    return re.sub(r"\d+", lambda m: m.group()[::-1], reversed_str)


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return ""
    if len(digits) == 9:
        digits = "0" + digits
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:]}"
    return _clean(value)


def _amount(value: str) -> float:
    token = _clean(value).replace(",", "").replace("₪", "").replace('ש"ח', "")
    try:
        return float(token)
    except Exception:
        return 0.0


def _detect(raw_text: str, fixed_text: str) -> bool:
    return (
        ("אקוסיטי" in fixed_text and "חשבונית יש להפיק עבור" in fixed_text)
        or ("יטיסוקא" in raw_text and "תינובשח" in raw_text)
    )


def _extract_po_date(lines: list[str]) -> str:
    if not lines:
        return ""
    match = re.search(r"(\d{2}/\d{2}/\d{2,4})", lines[0])
    return normalize_date(match.group(1)) if match else ""


def _extract_po_number(flat: str) -> str:
    match = re.search(r"רוקמ\s*-\s*([0-9/]+)\s+'סמ הנמזה", flat)
    if match:
        return _clean(match.group(1))
    return ""


def _extract_project(flat: str) -> str:
    match = re.search(r"'סמ הנמזה\s*-\s*(.+?)\s+טקיורפ", flat)
    if match:
        return _reverse_text(match.group(1))
    return ""


def _extract_customer_name(flat: str) -> str:
    match = re.search(r"(.+?)\s*:רובע קיפהל שי תינובשח", flat)
    if match:
        return _reverse_text(match.group(1))
    return CUSTOMER_NAME


def _extract_delivery_address(lines: list[str], project: str) -> str:
    for index, line in enumerate(lines):
        if line != "רתא יטרפ דובכל":
            continue
        city_line = lines[index + 3] if index + 3 < len(lines) else ""
        city = "תל אביב" if "ביבא לת" in city_line else _reverse_text(city_line)
        city = re.sub(r"\bנייד\b.*$", "", city).strip(" ,")
        city = re.sub(r"\b\d[\d\-]*\b", "", city).strip(" ,")
        city = _clean(city)
        if city == "תל אביב תל אביב":
            city = "תל אביב"

        parts = [part for part in [project, city] if part]
        if parts:
            return ", ".join(parts)
    return ""


def _extract_contacts(lines: list[str]) -> tuple[str, str, str, str]:
    """Return (primary_name, primary_phone, secondary_name, secondary_phone)."""
    phone_line = next((line for line in lines if line.startswith("052") or line.startswith("050") or ":לט" in line), "")
    if not phone_line:
        return "", "", "", ""

    contacts: list[tuple[str, str]] = []
    first_match = re.search(r"(0\d{9})\s+([^\s,]+)", phone_line)
    if first_match:
        contacts.append((_reverse_text(first_match.group(2)), _normalize_phone(first_match.group(1))))
    second_match = re.search(r",(0\d{2}-\d{7}),([^,\s:]+)", phone_line)
    if second_match:
        contacts.append((_reverse_text(second_match.group(2)), _normalize_phone(second_match.group(1))))

    deduped: list[tuple[str, str]] = []
    for name, phone in reversed(contacts):
        if any(existing_phone == phone for _, existing_phone in deduped):
            continue
        deduped.append((name, phone))

    # Only keep contacts that have a phone number
    valid = [(n, p) for n, p in deduped if p]
    if not valid:
        return "", "", "", ""
    p1_name, p1_phone = sanitize_contact_pair(valid[0][0], valid[0][1])
    if len(valid) >= 2:
        p2_name, p2_phone = sanitize_contact_pair(valid[1][0], valid[1][1])
    else:
        p2_name, p2_phone = "", ""
    return p1_name, p1_phone, p2_name, p2_phone


def _extract_item(lines: list[str]) -> POItem:
    for line in lines:
        if "FLSEC500" not in line:
            continue
        amounts = re.findall(r"([0-9,]+\.\d{2,3})", line)
        sku_match = re.search(r"-([A-Z0-9]+)\s*$", line)
        sku = sku_match.group(1) if sku_match else "FLSEC500"

        # Ecocity lines are extracted in reverse visual order:
        # total, unit price, quantity, unit, reversed description, SKU.
        item_match = re.search(
            r"([0-9,]+\.\d{2,3})\s+([0-9,]+\.\d{2,3})\s+(\d+(?:\.\d+)?)\s+(.+?)\s+-[A-Z0-9]+\s*$",
            line,
        )

        description = "פריט לא זוהה"
        quantity = 0.0
        unit_price = _amount(amounts[1]) if len(amounts) >= 2 else 0.0
        line_total = _amount(amounts[0]) if len(amounts) >= 1 else 0.0

        if item_match:
            quantity = float(item_match.group(3))
            desc_with_unit = _clean(item_match.group(4))
            desc_with_unit = re.sub(r'^["\'׳]?(?:חי|יח|ר"מ|מ"ר)\s+', "", desc_with_unit).strip()
            description = _reverse_text(desc_with_unit)

        return POItem(
            sku=sku,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
            unit='מ"ר',
        )

    return POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="", unit="")


def parse(text: str):
    raw_text = text or ""
    fixed_text = _reverse_text(raw_text)
    if not _detect(raw_text, fixed_text):
        return None

    lines = [_clean(line) for line in raw_text.splitlines() if _clean(line)]
    flat = "\n".join(lines)

    po_date = _extract_po_date(lines)
    po_number = _extract_po_number(flat)
    project = _extract_project(flat)
    customer_name = _extract_customer_name(flat)
    delivery_address = _extract_delivery_address(lines, project)
    contact_name, contact_phone, secondary_contact_name, secondary_contact_phone = _extract_contacts(lines)
    item = _extract_item(lines)

    payment_match = re.search(r"([0-9]+)\+ףטוש", flat)
    payment_days = int(payment_match.group(1)) if payment_match else None
    payment_label = f"שוטף + {payment_days}" if payment_days is not None else ""

    subtotal = item.line_total or 0.0
    vat = round(subtotal * 0.18, 2) if subtotal else 0.0
    total = round(subtotal + vat, 2) if subtotal else 0.0

    header = {
        "customer_email": "",
        "customer_id": CUSTOMER_ID,
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
        "secondary_contact_name": secondary_contact_name,
        "secondary_contact_phone": secondary_contact_phone,
        "customer_phone": "",
    }

    return customer_name or CUSTOMER_NAME, [item], header
