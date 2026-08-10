import re
from typing import Optional

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws, sanitize_contact_pair


CUSTOMER_NAME = 'הייקון (א.ק.) בע"מ'
CUSTOMER_ID = "516193430"


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"[\u200e\u200f\u202a-\u202e\ufeff]", "", text or "")
    return cleaned.replace("\r", "\n").replace("\x00", " ")


def _amount(value: str) -> float:
    token = re.sub(r"[^\d.]", "", (value or "").replace(",", ""))
    try:
        return float(token) if token else 0.0
    except ValueError:
        return 0.0


def _first(pattern: str, text: str, flags=re.MULTILINE | re.IGNORECASE) -> str:
    match = re.search(pattern, text, flags)
    return normalize_ws(match.group(1)) if match else ""


def _normalize_dimension(value: str) -> str:
    value = normalize_ws(value).replace(" ", "")
    if value.startswith(("+-", "-+")):
        return f"+-{value[2:]}"
    return value


def _extract_items(text: str) -> list[POItem]:
    items: list[POItem] = []
    row_pattern = re.compile(
        r"(?P<dimension>[+\-]*\d{3,4}/\d{3,4})"
        r"[^\n]*?[ \t]+(?P<quantity>\d+(?:\.\d{1,2})?)"
        r"[ \t]+(?P<unit_price>\d+(?:\.\d{1,2})?)"
        r"[ \t]+[^\n]*?[ \t]+(?P<discount>\d+(?:\.\d{1,2})?)"
        r"[ \t]+(?P<line_total>\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?)[ \t]*$",
        re.MULTILINE,
    )

    sku_root_match = re.search(r"1700[-\s]?PROD[0O]5", text, re.IGNORECASE)
    reversed_sku_match = re.search(r"PROD[0O]5[-\s]?1700", text, re.IGNORECASE)
    if sku_root_match:
        sku_root = sku_root_match.group(0).upper().replace(" ", "-")
    elif reversed_sku_match:
        sku_root = "1700-PROD05"
    else:
        sku_root = ""
    sku_root = re.sub(r"(?<=PROD)O(?=5$)", "0", sku_root)
    has_sku_continuation = bool(re.search(r"(?m)^\s*0?500\s*$", text))
    sku = f"{sku_root}0500" if sku_root and has_sku_continuation else sku_root

    for match in row_pattern.finditer(text):
        dimension = _normalize_dimension(match.group("dimension"))
        quantity = _amount(match.group("quantity"))
        unit_price = _amount(match.group("unit_price"))
        line_total = _amount(match.group("line_total"))
        if not quantity or not unit_price or not line_total:
            continue
        items.append(
            POItem(
                sku=sku,
                description=f"יח' מגן דלת / כנף {dimension}",
                quantity=quantity,
                unit="יח'",
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    if items:
        return items

    # Google Drive OCR preserves all values but may emit table columns as separate
    # vertical blocks. Reassemble the three rows by their document order and verify
    # every quantity/price/total relation before accepting the fallback.
    dimension_matches = list(re.finditer(r"[+\-]*\d{3,4}/\d{3,4}", text))
    dimensions = [_normalize_dimension(match.group(0)) for match in dimension_matches]
    if not dimensions:
        return []

    numeric_block = ""
    last_dimension_end = dimension_matches[-1].end()
    delivery_marker = re.search(r"מקום\s+אספקה", text[last_dimension_end:])
    if delivery_marker:
        numeric_block = text[
            last_dimension_end:last_dimension_end + delivery_marker.start()
        ]
    price_quantity_values = [
        _amount(value)
        for value in re.findall(r"(?m)^\s*(\d+(?:\.\d{2})?)\s*$", numeric_block)
    ]

    totals_block = ""
    totals_start = re.search(r"מטבע\s*%?\s*הנחה", text)
    if totals_start:
        after_totals_start = text[totals_start.end():]
        totals_end = re.search(r"סה[\"״']?כ\s*:", after_totals_start)
        totals_block = (
            after_totals_start[:totals_end.start()]
            if totals_end
            else after_totals_start
        )
    line_totals = [
        _amount(value)
        for value in re.findall(
            r"(?m)^\s*(\d{1,3}(?:,\d{3})+\.\d{2})\s*$",
            totals_block,
        )
    ]

    row_count = len(dimensions)
    if len(price_quantity_values) < row_count * 2 or len(line_totals) < row_count:
        return []
    for index, dimension in enumerate(dimensions):
        unit_price = price_quantity_values[index * 2]
        quantity = price_quantity_values[index * 2 + 1]
        line_total = line_totals[index]
        if round(quantity * unit_price, 2) != round(line_total, 2):
            return []
        items.append(
            POItem(
                sku=sku,
                description=f"יח' מגן דלת / כנף {dimension}",
                quantity=quantity,
                unit="יח'",
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    return items


def _extract_totals(text: str, items: list[POItem]) -> tuple[float, float, float]:
    subtotal = _amount(
        _first(r"סה[\"״']?כ\s+לפני\s+.*?([\d,]+(?:\.\d{1,2})?)", text)
        or _first(r"סה[\"״']?כ\s*:\s*([\d,]+(?:\.\d{1,2})?)", text)
    )
    vat = _amount(
        _first(r"(?:מע[\"״']?מ|מ.?ע.?מ).*?18(?:\.00)?\s*%?\s*\|?\s*([\d,]+(?:\.\d{1,2})?)", text)
    )
    total = _amount(_first(r"סה[\"״']?כ\s+לתשלום\s*:\s*([\d,]+(?:\.\d{1,2})?)", text))

    calculated_subtotal = round(sum(item.line_total for item in items), 2)
    subtotal = subtotal or calculated_subtotal
    total = total or (round(subtotal + vat, 2) if subtotal and vat else 0.0)
    vat = vat or (round(total - subtotal, 2) if total and subtotal else 0.0)
    return subtotal, vat, total


def parse(text: str) -> Optional[tuple[str, list[POItem], dict]]:
    clean = _clean_text(text)
    is_haikon = CUSTOMER_ID in clean or (
        "מישור אדומים" in clean
        and "הזמנת רכש" in clean
        and ("חשבשבת" in clean or "ERP" in clean)
    )
    if not is_haikon:
        return None

    items = _extract_items(clean)
    if not items:
        return None

    po_number = _first(
        r"הזמנת\s+רכש\s+מס[\"״']?[ \t]*:[ \t]*([A-Za-z0-9/-]+)",
        clean,
    )
    if not po_number:
        po_header = re.search(r"הזמנת\s+רכש\s+מס[\"״']?[ \t]*:", clean)
        if po_header:
            nearby_header = clean[po_header.end():po_header.end() + 250]
            po_number = _first(r"^\s*(\d{4,})\s*$", nearby_header)
    po_date = normalize_date(
        _first(r"(?:תאריך|NN)\s*:\s*(\d{1,2}/\d{1,2}/\d{4})", clean)
        or _first(r"(\d{1,2}/\d{1,2}/\d{4})", clean)
    )
    project = _first(r"פרו?י?יקט\s*:\s*([^\n]+)", clean)
    delivery_address = _first(r"מקום\s+אספקה\s*:\s*([^\n]+?)(?=\s+סה[\"״']?כ|$)", clean)
    if not delivery_address:
        delivery_address = _first(r"לספק\s+(?:ל)?(רחוב\s+[^/\n]+)", clean)

    contact_match = re.search(r"([^/\n\d]{2,30})\s+(05\d[-\s]?\d{7})", clean)
    contact_name = normalize_ws(contact_match.group(1)) if contact_match else ""
    contact_phone = normalize_ws(contact_match.group(2)) if contact_match else ""
    contact_name = re.sub(r"^(?:לספק.*?/{2,3}\s*)", "", contact_name).strip()
    contact_name, contact_phone = sanitize_contact_pair(contact_name, contact_phone)

    payment_terms_days = None
    payment_terms_label = ""
    payment_line = _first(r"תנאי\s+תשלום\s*:\s*([^\n]+)", clean)
    payment_match = re.search(r"(\d+)", payment_line)
    if payment_match:
        payment_terms_days = int(payment_match.group(1))
        payment_terms_label = f"שוטף {payment_terms_days}"

    subtotal, vat, total = _extract_totals(clean, items)
    customer_phone = _first(r"טל[\"״']?\s*:\s*(0\d[-\d]+)", clean)
    customer_fax = _first(r"פקס\s*:\s*(0\d[-\d]+)", clean)
    order_subject = _first(r"(?:הזמנה|זמנת)\s*:\s*([^\n]+?)(?=\s+שעה\s*:|$)", clean)

    header = {
        "customer_name": CUSTOMER_NAME,
        "customer_id": CUSTOMER_ID,
        "customer_phone": customer_phone,
        "customer_email": "",
        "delivery_address": delivery_address,
        "po_number": po_number,
        "po_date": po_date,
        "subtotal": subtotal,
        "vat": vat,
        "total": total,
        "project": project,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "payment_terms_days": payment_terms_days,
        "payment_terms_label": payment_terms_label,
        "extra": {
            "customer_fax": customer_fax,
            "order_subject": order_subject,
            "supplier_customer_number": _first(r"מזהה\s*:\s*(\d+)", clean),
            "supplier_id": _first(r"ע\.?מ\.?\s*(\d{8,9})", clean),
        },
    }
    return CUSTOMER_NAME, items, header
