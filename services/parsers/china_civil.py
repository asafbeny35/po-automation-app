import re
from typing import Optional

from services.models import POItem, PurchaseOrderData
from services.parsers.common import fix_hebrew_rtl_text, normalize_date, normalize_ws, to_purchase_order


CUSTOMER_NAME = "צ'יינה סיביל אינג'נירינג"
CUSTOMER_ID = "560024093"


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


def _normalize_unit(value: str) -> str:
    unit = normalize_ws(value).replace("׳", "'").replace("״", '"')
    if unit in {"יח", "יחידה"}:
        return "יח'"
    return unit


def _extract_contacts(raw_text: str, fixed_text: str) -> tuple[str, str, str, str]:
    reversed_match = re.search(
        r"(05\d{1,2}-\d{3}-\d{4})\s+([א-ת'״\"\- ]+?),"
        r"\s*(05\d{1,2}-\d{3}-\d{4})\s+([א-ת'״\"\- ]+?)\s*:לט",
        raw_text,
    )
    if reversed_match:
        secondary_phone, secondary_name, primary_phone, primary_name = reversed_match.groups()
        return (
            normalize_ws(primary_name[::-1]),
            primary_phone,
            normalize_ws(secondary_name[::-1]),
            secondary_phone,
        )

    normal_match = re.search(
        r"טל\s*:\s*([^,\d\n]+?)\s+(05\d{1,2}-\d{3}-\d{4})\s*,\s*"
        r"([^,\d\n]+?)\s+(05\d{1,2}-\d{3}-\d{4})",
        fixed_text,
    )
    if normal_match:
        primary_name, primary_phone, secondary_name, secondary_phone = normal_match.groups()
        return (
            normalize_ws(primary_name),
            primary_phone,
            normalize_ws(secondary_name),
            secondary_phone,
        )

    return "", "", "", ""


def _extract_site_details(fixed_lines: list[str]) -> tuple[str, str]:
    supplier_index = next(
        (index for index, line in enumerate(fixed_lines) if "בן יעקב פתרונות טקסטיל" in line),
        None,
    )
    if supplier_index is None:
        return "", ""

    supplier_line = fixed_lines[supplier_index]
    site_name = normalize_ws(supplier_line.split("בן יעקב פתרונות טקסטיל", 1)[-1])
    address_parts: list[str] = []
    for line in fixed_lines[supplier_index + 1 :]:
        if line.startswith("טל:") or "פריט כמות" in line:
            break
        if line and line not in {"לכבוד", "פרטי אתר"}:
            address_parts.append(line)

    delivery_address = ", ".join(dict.fromkeys(address_parts))
    return site_name, delivery_address or site_name


def _is_item_row(line: str) -> bool:
    return bool(
        re.match(
            r"^\s*-?[A-Z][A-Z0-9_-]*\d\s+.+?\s+"
            r"(?:יח['׳]?|מ[\"״]ר|יחידה|מטר)\s+"
            r"[\d,.]+\s+[\d,.]+\s+[\d,.]+(?:\s+.*)?$",
            line,
        )
    )


def _extract_items(fixed_lines: list[str]) -> list[POItem]:
    items: list[POItem] = []
    row_pattern = re.compile(
        r"^\s*-?(?P<sku>[A-Z][A-Z0-9_-]*\d)\s+"
        r"(?P<description>.+?)\s+"
        r"(?P<unit>יח['׳]?|מ[\"״]ר|יחידה|מטר)\s+"
        r"(?P<quantity>[\d,.]+)\s+"
        r"(?P<unit_price>[\d,.]+)\s+"
        r"(?P<line_total>[\d,.]+)(?:\s+.*)?$"
    )

    for index, line in enumerate(fixed_lines):
        match = row_pattern.match(line)
        if not match:
            continue

        continuation: list[str] = []
        for next_line in fixed_lines[index + 1 :]:
            if _is_item_row(next_line) or any(
                marker in next_line
                for marker in ("תנאי תשלום", "סה\"כ הזמנה", "חשבונית יש להפיק עבור")
            ):
                break
            if next_line.startswith(("פריט ", "QRLabel", "קוד ")):
                continue
            if next_line and not re.match(r"^\.?\d+\s", next_line):
                continuation.append(next_line)

        description = normalize_ws(" ".join([match.group("description"), *continuation]))
        items.append(
            POItem(
                sku=match.group("sku").lstrip("-"),
                description=description,
                unit=_normalize_unit(match.group("unit")),
                quantity=_amount(match.group("quantity")),
                unit_price=_amount(match.group("unit_price")),
                line_total=_amount(match.group("line_total")),
            )
        )

    return items


def parse(text: str) -> Optional[PurchaseOrderData]:
    raw_text = _clean_text(text)
    is_china_civil = CUSTOMER_ID in raw_text and any(
        marker in raw_text
        for marker in ("ליביס הניי'צ", "צ'יינה סיביל", "חשבונית יש להפיק", "תינובשח")
    )
    if not is_china_civil:
        return None

    fixed_text = fix_hebrew_rtl_text(raw_text) if "טקיורפ" in raw_text else raw_text
    fixed_lines = [normalize_ws(line) for line in fixed_text.splitlines() if normalize_ws(line)]

    po_number = _first(r"הזמנה\s+מס['׳]?\s*-?\s*([0-9]+/[0-9]+)", fixed_text)
    if not po_number:
        po_number = _first(r"([0-9]+/[0-9]+)\s+['׳]?סמ\s+הנמזה", raw_text)

    po_date = normalize_date(_first(r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b", raw_text))
    project = _first(r"פרויקט\s+(.+?)\s+-\s+הזמנה\s+מס", fixed_text)
    site_name, delivery_address = _extract_site_details(fixed_lines)
    primary_name, primary_phone, secondary_name, secondary_phone = _extract_contacts(raw_text, fixed_text)
    items = _extract_items(fixed_lines)
    if not items:
        return None

    payment_days_match = re.search(r"(\d+)\+ףטוש", raw_text)
    if not payment_days_match:
        payment_days_match = re.search(r"שוטף\s*\+?\s*(\d+)", fixed_text)
    payment_days = int(payment_days_match.group(1)) if payment_days_match else None

    subtotal = _amount(
        _first(r"([\d,.]+)\s*:\s*הנמזה\s+כ[\"״]הס", raw_text)
        or _first(r"סה[\"״]כ\s+הזמנה\s*:\s*([\d,.]+)", fixed_text)
    )
    subtotal = subtotal or round(sum(item.line_total for item in items), 2)
    vat = round(subtotal * 0.18, 2)
    total = round(subtotal + vat, 2)

    customer_match = re.search(
        r"חשבונית\s+יש\s+להפיק\s+עבור\s*:\s*(.+?)\s*-?\s*ח\.פ\.?\s*(\d{9})",
        fixed_text,
    )
    customer_name = CUSTOMER_NAME
    customer_id = CUSTOMER_ID
    if customer_match:
        customer_name = normalize_ws(customer_match.group(1)).rstrip("- ") or CUSTOMER_NAME
        customer_id = customer_match.group(2)

    header = {
        "customer_name": customer_name,
        "customer_id": customer_id,
        "customer_email": "",
        "customer_phone": "",
        "delivery_address": delivery_address,
        "po_number": po_number,
        "po_date": po_date,
        "subtotal": subtotal,
        "vat": vat,
        "total": total,
        "project": project,
        "contact_name": primary_name,
        "contact_phone": primary_phone,
        "payment_terms_days": payment_days,
        "payment_terms_label": f"שוטף + {payment_days}" if payment_days is not None else "",
    }
    purchase_order = to_purchase_order(customer_name, items, header, raw_text)
    purchase_order.secondary_contact_name = secondary_name
    purchase_order.secondary_contact_phone = secondary_phone
    purchase_order.extra = {
        **dict(purchase_order.extra or {}),
        "secondary_contact_name": secondary_name,
        "secondary_contact_phone": secondary_phone,
        "site_name": site_name,
        "prices_exclude_vat": True,
        "source_template": "ZivPdf",
        "order_author": _first(r"([A-Za-z][A-Za-z ]+?)\s*:י[\"״]ע\s+הקפוה\s+וז\s+הנמזה", raw_text),
    }
    return purchase_order
