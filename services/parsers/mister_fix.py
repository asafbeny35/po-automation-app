import re
from typing import Optional

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws


CUSTOMER_NAME = 'כרמית מיסטר פיקס בע"מ'
CUSTOMER_ID = "511493306"
VAT_GROUP_ID = "557586161"


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


def _extract_item_identities(text: str) -> list[tuple[str, str]]:
    pattern = re.compile(
        r"(?ms)^\s*\d+\s*\|?\s*(?P<sku>\d{5,})\s*\|?\s*"
        r"(?P<description>.+?)"
        r"(?=^\s*\d+\s*\|?\s*\d{5,}\s*\|?|^\s*ברקוד\s+מספר\s+תעודה|\Z)"
    )
    identities: list[tuple[str, str]] = []
    for match in pattern.finditer(text):
        description = normalize_ws(match.group("description"))
        # Some OCR providers keep the numeric columns on the same line. They are
        # parsed separately below and must not leak into the product description.
        description = re.split(
            r"\s+(?:\d{1,3}(?:,\d{3})+\.\d{2}\s+ILS|\d{1,2}/\d{1,2}/\d{2,4}\s+\d)",
            description,
            maxsplit=1,
        )[0].strip(" |-:")
        if description:
            identities.append((match.group("sku"), description))
    return identities


def _extract_numeric_rows(text: str) -> list[tuple[float, float, float, str]]:
    amount = r"\d{1,3}(?:,\d{3})*(?:\.\d{1,3})?"
    date = r"\d{1,2}/\d{1,2}/\d{2,4}"
    patterns = (
        # Google/OpenAI OCR for the supplied scan: total, currency, unit price,
        # unit, quantity, requested delivery date.
        re.compile(
            rf"(?P<total>{amount})\s+ILS\s+(?P<price>{amount})\s+\S{{1,6}}\s+"
            rf"(?P<quantity>{amount})\s+(?P<date>{date})\s*$",
            re.IGNORECASE,
        ),
        # Conventional visual order: delivery date, quantity, unit, unit price,
        # optional currency, and line total.
        re.compile(
            rf"(?P<date>{date})\s+(?P<quantity>{amount})\s+\S{{1,6}}\s+"
            rf"(?:ILS\s+)?(?P<price>{amount})\s+(?:ILS\s+)?(?P<total>{amount})\s*$",
            re.IGNORECASE,
        ),
    )

    rows: list[tuple[float, float, float, str]] = []
    for raw_line in text.splitlines():
        line = normalize_ws(raw_line)
        if not line or not re.search(date, line):
            continue
        match = None
        for pattern in patterns:
            match = pattern.search(line)
            if match:
                break
        if not match:
            continue
        quantity = _amount(match.group("quantity"))
        unit_price = _amount(match.group("price"))
        line_total = _amount(match.group("total"))
        if not quantity or not unit_price or not line_total:
            continue
        if abs(quantity * unit_price - line_total) > 0.02:
            continue
        rows.append(
            (
                quantity,
                unit_price,
                line_total,
                normalize_date(match.group("date")),
            )
        )
    return rows


def _extract_items(text: str) -> tuple[list[POItem], list[dict[str, str]]]:
    identities = _extract_item_identities(text)
    numeric_rows = _extract_numeric_rows(text)
    if not identities or len(identities) != len(numeric_rows):
        return [], []

    items: list[POItem] = []
    delivery_dates: list[dict[str, str]] = []
    for (sku, description), (quantity, unit_price, line_total, delivery_date) in zip(
        identities, numeric_rows
    ):
        items.append(
            POItem(
                sku=sku,
                description=description,
                quantity=quantity,
                unit="יח'",
                unit_price=unit_price,
                line_total=line_total,
            )
        )
        delivery_dates.append({"sku": sku, "date": delivery_date})
    return items, delivery_dates


def _extract_summary_amounts(text: str) -> tuple[float, float, float]:
    lines = [normalize_ws(line) for line in text.splitlines()]
    for index, line in enumerate(lines):
        if "מחיר כולל" not in line:
            continue
        values: list[float] = []
        for candidate in lines[index + 1:index + 10]:
            match = re.fullmatch(r"(?:ILS\s*)?(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)", candidate)
            if match:
                values.append(_amount(match.group(1)))
        if len(values) >= 3:
            return values[0], values[1], values[2]

    subtotal = _amount(
        _first(
            r"(?:מחיר\s+כולל|סה[\"״']?כ\s+לפני\s+מע[\"״']?מ)"
            r"[ \t]*:?[ \t]*(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
            text,
        )
    )
    vat = _amount(
        _first(
            r"מע[\"״']?מ(?:[ \t]*\([^\n)]*\))?[ \t]*:?[ \t]*"
            r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
            text,
        )
    )
    total = _amount(
        _first(
            r"סה[\"״']?[כייה]+\s+מחיר[ \t]*:?[ \t]*(?:ILS[ \t]*)?"
            r"(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)",
            text,
        )
    )
    return subtotal, vat, total


def _totals(text: str, items: list[POItem]) -> tuple[float, float, float]:
    extracted_subtotal, extracted_vat, extracted_total = _extract_summary_amounts(text)
    calculated_subtotal = round(sum(item.line_total for item in items), 2)
    subtotal = (
        extracted_subtotal
        if abs(extracted_subtotal - calculated_subtotal) <= 0.02
        else calculated_subtotal
    )

    vat_rate = _amount(_first(r"מע[\"״']?מ\s*\((\d+(?:\.\d+)?)\s*%", text)) or 18.0
    calculated_vat = round(subtotal * vat_rate / 100, 2)
    vat = extracted_vat if abs(extracted_vat - calculated_vat) <= 0.02 else calculated_vat
    calculated_total = round(subtotal + vat, 2)
    total = extracted_total if abs(extracted_total - calculated_total) <= 0.02 else calculated_total
    return subtotal, vat, total


def _customer_address(text: str) -> str:
    match = re.search(
        r"ת\.?\s*ד\.?\s*(\d+)\s+([^\n]+)\n\s*([^\n]+?)\s+טלפון\s*:",
        text,
        re.IGNORECASE,
    )
    if not match:
        return ""
    post_office_box, first_location, second_location = (
        normalize_ws(match.group(1)),
        normalize_ws(match.group(2)),
        normalize_ws(match.group(3)),
    )
    return f"ת.ד {post_office_box} {first_location}, {second_location}"


def parse(text: str) -> Optional[tuple[str, list[POItem], dict]]:
    clean = _clean_text(text)
    is_mister_fix = (
        CUSTOMER_ID in clean
        and any(marker in clean.lower() for marker in ("מיסטר פיקס", "mrfix.co.il"))
    ) or (
        VAT_GROUP_ID in clean
        and "הזמנת רכש" in clean
        and "פריוריטי" in clean
    )
    if not is_mister_fix:
        return None

    items, delivery_dates = _extract_items(clean)
    if not items:
        return None

    po_number = _first(r"הזמנת\s+רכש\s+מספר\s+(PO\d+)", clean)
    barcode_po_number = _first(
        r"ברקוד\s+מספר\s+תעודה\s*:\s*\*?([A-Z]{1,4}\d+)\*?",
        clean,
    )
    if po_number and barcode_po_number and po_number != barcode_po_number:
        return None
    po_number = po_number or barcode_po_number
    if not po_number:
        return None

    po_date = normalize_date(
        _first(r"תאריך\s+הזמנה\s*:\s*(\d{1,2}/\d{1,2}/\d{2,4})", clean)
    )
    payment_days = _first(
        r"תנאי\s+תשלום\s*:\s*(?:ש(?:וטף)?\s*\+?\s*)?(\d{1,3})",
        clean,
    )
    payment_terms_days = int(payment_days) if payment_days else None
    payment_terms_label = (
        f"שוטף + {payment_terms_days}" if payment_terms_days is not None else ""
    )
    subtotal, vat, total = _totals(clean, items)

    requested_dates = {entry["date"] for entry in delivery_dates if entry["date"]}
    requested_delivery_date = (
        next(iter(requested_dates)) if len(requested_dates) == 1 else ""
    )
    document_status = _first(
        r"הזמנת\s+רכש\s+מספר\s+PO\d+\s*-\s*([^\n]+)",
        clean,
    )

    header = {
        "customer_name": CUSTOMER_NAME,
        "customer_id": CUSTOMER_ID,
        "customer_phone": _first(r"טלפון\s*:\s*(0\d[-\d]+)", clean),
        "customer_email": _first(r"e-?mail\s*:\s*([^\s]+@[^\s]+)", clean),
        # The document contains the customer's registered address, not an explicit
        # delivery destination. Do not fabricate a delivery address from it.
        "delivery_address": "",
        "po_number": po_number,
        "po_date": po_date,
        "subtotal": subtotal,
        "vat": vat,
        "total": total,
        "project": "",
        "contact_name": "",
        "contact_phone": "",
        "payment_terms_days": payment_terms_days,
        "payment_terms_label": payment_terms_label,
        "extra": {
            "customer_address": _customer_address(clean),
            "vat_group_id": _first(
                r"מספר\s+תיק\s+במע[\"״']?מ\s*:\s*(\d{8,9})", clean
            ),
            "withholding_file_number": _first(
                r"מס\.?\s+תיק\s+ניכויים\s*:\s*(\d{8,9})", clean
            ),
            "supplier_customer_number": _first(r"מס[\"״']?\s+ספק\s*:\s*(\d+)", clean),
            "recipient_business_id": _first(
                r"מס\.?\s+עוסק\s+מורשה\s*:\s*(\d{8,9})", clean
            ),
            "document_barcode": barcode_po_number,
            "document_status": document_status,
            "current_revision": _first(r"מהדורה\s+נוכחית\s*:\s*(\d+)", clean),
            "requested_delivery_date": requested_delivery_date,
            "item_delivery_dates": delivery_dates,
            "source_system": "Priority",
        },
    }
    return CUSTOMER_NAME, items, header
