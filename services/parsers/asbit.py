import re

from services.models import POItem
from services.parsers.common import fix_hebrew_text, normalize_date, normalize_ws


CUSTOMER_NAME = 'אסביט'
CUSTOMER_ID = "513208256"


def _parse_amount(value: str) -> float:
    cleaned = re.sub(r"[^\d.,-]", "", str(value or "").strip()).replace(",", "")
    return float(cleaned) if cleaned else 0.0


def _clean_description(value: str) -> str:
    text = normalize_ws(str(value or ""))
    text = text.replace("epiPteiuQ", "QuietPipe")
    text = text.replace(") QuietPipe (", "(QuietPipe)")
    text = text.replace("( QuietPipe )", "(QuietPipe)")
    text = text.replace("2X1", "1X2")
    text = text.replace("  ", " ")
    return normalize_ws(text).strip(" -") or "פריט לא זוהה"


def parse(text: str):
    raw_text = str(text or "")
    fixed_text = fix_hebrew_text(raw_text)
    if "אסביט" not in fixed_text or "הזמנת רכש" not in fixed_text:
        return None

    raw_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    fixed_lines = [line.strip() for line in fixed_text.splitlines() if line.strip()]

    header = {
        "customer_email": "",
        "customer_id": CUSTOMER_ID,
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
    }

    po_match = re.search(r"([0-9]{4,})\s*:\s*['׳]?\s*סמ שכר תנמזה", raw_text)
    if po_match:
        header["po_number"] = po_match.group(1).strip()

    date_match = re.search(r"([0-9]{2}/[0-9]{2}/[0-9]{2,4})\s*:\s*ךיראת", raw_text)
    if date_match:
        header["po_date"] = normalize_date(date_match.group(1))

    subtotal_match = re.search(r"סה\"?כ לפני מע\"?מ\s*:?([0-9,]+\.\d{2})", fixed_text)
    if not subtotal_match:
        subtotal_match = re.search(r"([0-9,]+\.\d{2})\s*:מ\"עמ ינפל כ\"הס", raw_text)
    if subtotal_match:
        header["subtotal"] = _parse_amount(subtotal_match.group(1))

    vat_match = re.search(r"18\.00\s*%\s*מע\"?מ\s*:?([0-9,]+\.\d{2})", fixed_text)
    if not vat_match:
        vat_match = re.search(r"([0-9,]+\.\d{2})\s*:מ\"עמ\s*18\.00\s*%", raw_text)
    if vat_match:
        header["vat"] = _parse_amount(vat_match.group(1))

    total_match = re.search(r"סה\"?כ לתשלום\s*:?([0-9,]+\.\d{2})", fixed_text)
    if not total_match:
        total_match = re.search(r"([0-9,]+\.\d{2})\s*:םולשתל כ\"הס", raw_text)
    if total_match:
        header["total"] = _parse_amount(total_match.group(1))

    address_lines = []
    for index, line in enumerate(fixed_lines):
        if "*** אספקה לסניף פתח תקוה רחוב בר" in line:
            address_lines.append(line.replace("***", "").strip())
            if index + 1 < len(fixed_lines):
                address_lines.append(fixed_lines[index + 1].replace("***", "").strip())
            break
    if address_lines:
        address = " ".join(address_lines)
        address = address.replace("אספקה לסניף ", "").strip()
        header["delivery_address"] = normalize_ws(address)

    item = POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="", unit="")
    raw_item_line = next((line for line in raw_lines if "QuietPipe" in line and re.search(r"\d{10}", line)), "")
    raw_item_continuation = ""
    if raw_item_line:
        try:
            idx = raw_lines.index(raw_item_line)
            raw_item_continuation = raw_lines[idx + 1] if idx + 1 < len(raw_lines) else ""
        except Exception:
            raw_item_continuation = ""

    fixed_item_line = next((line for line in fixed_lines if "epiPteiuQ" in line and re.search(r"\d{10}", line)), "")
    fixed_item_continuation = ""
    if fixed_item_line:
        try:
            idx = fixed_lines.index(fixed_item_line)
            fixed_item_continuation = fixed_lines[idx + 1] if idx + 1 < len(fixed_lines) else ""
        except Exception:
            fixed_item_continuation = ""

    sku_match = re.search(r"(\d{10})", raw_item_line or fixed_item_line)
    sku = sku_match.group(1).strip() if sku_match else ""

    quantity = 0.0
    unit_price = 0.0
    line_total = 0.0
    structured_match = re.search(
        r"([0-9]+\.\d{2})\s+([0-9]+\.\d{2})\s+([0-9]+\.\d{2})\s+([0-9]+\.\d{2})\s+([0-9]+\.\d{2})\s+.+?\s+\d{10}",
        raw_item_line,
    )
    if structured_match:
        line_total = _parse_amount(structured_match.group(1))
        unit_price = _parse_amount(structured_match.group(4))
        quantity = _parse_amount(structured_match.group(5))

    description = ""
    if fixed_item_line:
        description_match = re.search(r"\d{10}\s+(.+?)\s+00\.5\s+00\.611\s+00\.0\s+00\.611\s+00\.085", fixed_item_line)
        if description_match:
            description = description_match.group(1).strip()
    if fixed_item_continuation:
        description = f"{description} {fixed_item_continuation}".strip()
    description = _clean_description(description)

    if sku or description != "פריט לא זוהה":
        item = POItem(
            sku=sku,
            description=description,
            quantity=quantity or 1.0,
            unit_price=unit_price,
            line_total=line_total or header["subtotal"] or round((quantity or 0) * unit_price, 2),
            unit="יחידה",
        )

    if not header["subtotal"] and item.line_total:
        header["subtotal"] = item.line_total
    if not header["vat"] and header["subtotal"]:
        header["vat"] = round(header["subtotal"] * 0.18, 2)
    if not header["total"] and header["subtotal"]:
        header["total"] = round(header["subtotal"] + header["vat"], 2)

    return CUSTOMER_NAME, [item], header
