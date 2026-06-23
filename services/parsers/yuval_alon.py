import re
from typing import Optional

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws


CUSTOMER_NAME = 'יובל אלון פרוייקטים בנדל"ן בע"מ'
CUSTOMER_ID = "513013359"
REVERSED_MARKERS = ("שכר תנמזה", "ןולא לבוי", "טירפ רואית")


def _clean_text(text: str) -> str:
    return re.sub(r"[\u200e\u200f\u202a-\u202e]", "", text or "").replace("\r", "\n")


def _normalize_amount(value: str) -> float:
    raw = normalize_ws(value).replace(",", "")
    raw = raw.replace("₪", "").replace('ש"ח', "").replace("שח", "").strip()
    raw = re.sub(r"[^\d.]", "", raw)
    try:
        return float(raw) if raw else 0.0
    except Exception:
        return 0.0


def _find_first(pattern: str, text: str, flags=re.MULTILINE):
    match = re.search(pattern, text, flags)
    return match.group(1).strip() if match else ""


def _restore_reversed_line(line: str) -> str:
    tokens = line.split()
    if not tokens:
        return ""
    restored_tokens = []
    for token in reversed(tokens):
        if re.search(r"[א-ת]", token):
            token = token[::-1]
        restored_tokens.append(token)
    restored = " ".join(restored_tokens)
    restored = re.sub(r"\s+,", ",", restored)
    restored = re.sub(r"\s+:", ":", restored)
    restored = re.sub(r"\s+/", " /", restored)
    restored = re.sub(r"(\d)\s*,\s*(\d)", r"\1, \2", restored)
    return normalize_ws(restored)


def _normalize_source_text(text: str) -> str:
    cleaned = _clean_text(text)
    if "הזמנת רכש" in cleaned and "יובל אלון" in cleaned:
        return cleaned
    if not any(marker in cleaned for marker in REVERSED_MARKERS):
        return cleaned
    restored_lines = [_restore_reversed_line(line) for line in cleaned.splitlines()]
    return "\n".join(line for line in restored_lines if normalize_ws(line))


def _extract_project(text: str) -> str:
    project_line = _find_first(r"פרויקט\s*:\s*([^\n]+)", text)
    compound_line = _find_first(r"מתחם\s*:\s*([^\n]+)", text)
    parts = [normalize_ws(project_line), normalize_ws(compound_line)]
    return " | ".join(part for part in parts if part)


def _extract_delivery_contact(text: str) -> tuple[str, str, str]:
    match = re.search(
        r"תאריך אספקה\s*:?\s*([0-9./]+)\s+(.+?,\s*[א-ת]+)\s+([א-ת\"׳' \-]+?)\s+(05\d{8})",
        text,
    )
    if not match:
        match = re.search(
            r"תאריך אספקה\s*:?\s*([0-9./]+)\s+(.+?)\s+([א-ת\"׳' \-]+?)\s+(05\d{8})",
            text,
        )
    if not match:
        return "", "", ""

    delivery_address = normalize_ws(match.group(2))
    delivery_address = re.sub(r"\s*,\s*", ", ", delivery_address)
    contact_name = normalize_ws(match.group(3))
    contact_phone = normalize_ws(match.group(4))
    return delivery_address, contact_name, contact_phone


def _extract_item(text: str) -> list[dict]:
    lines = [normalize_ws(line) for line in text.splitlines() if normalize_ws(line)]
    for index, line in enumerate(lines):
        match = re.search(
            r"^\d+\s+(.+?)\s+(\d+(?:\.\d+)?)\s*מ\"?ר\s*-\s*([\d.]+)\s+(\d+(?:\.\d+)?)\s*ש.?ח\s+(\d+(?:\.\d+)?)\s*ש.?ח$",
            line,
        )
        if not match:
            continue

        description = normalize_ws(match.group(1))
        quantity = _normalize_amount(match.group(2))
        unit_price = _normalize_amount(match.group(4))
        line_total = _normalize_amount(match.group(5))
        sku_line = lines[index + 1] if index + 1 < len(lines) else ""
        sku_match = re.search(r"\b(\d{4,})\b", sku_line)
        sku = normalize_ws(sku_match.group(1) if sku_match else "")

        return [{
            "description": description,
            "sku": sku,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
        }]
    return []


def parse_yuval_alon(text: str) -> Optional[dict]:
    source_text = _normalize_source_text(text)
    if "יובל אלון" not in source_text or "הזמנת רכש" not in source_text:
        return None

    po_number = _find_first(r"הזמנת רכש\s*(\d+)", source_text)
    po_date_raw = _find_first(r"תאריך שליחת ההזמנה\s*([0-9./]+)", source_text)
    po_date = normalize_date(po_date_raw.replace(".", "/")) if po_date_raw else ""

    project = _extract_project(source_text)
    delivery_address, contact_name, contact_phone = _extract_delivery_contact(source_text)
    items = _extract_item(source_text)

    customer_phone = _find_first(r"טל\s*:\s*(0\d{8,9})", source_text)
    subtotal = _normalize_amount(_find_first(r"סה.?כ לפני מע.?מ\s*:?\s*([0-9.,]+)", source_text))
    vat = _normalize_amount(_find_first(r"(?m)^מע.?מ\s*:?\s*([0-9.,]+)", source_text))
    total = _normalize_amount(_find_first(r"סה.?כ כולל מע.?מ\s*:?\s*([0-9.,]+)", source_text))

    footer_parts = []
    if CUSTOMER_ID:
        footer_parts.append(f'ח.פ / ע.מ: {CUSTOMER_ID}')
    if po_number:
        footer_parts.append(f"הזמנת רכש {po_number}")
    if project:
        footer_parts.append(f"פרויקט: {project}")
    if delivery_address:
        footer_parts.append(f"כתובת לאספקה: {delivery_address}")
    if contact_name:
        footer_parts.append(f"איש קשר: {contact_name}")
    if contact_phone:
        footer_parts.append(f"טל': {contact_phone}")

    return {
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
        "items": items,
        "extra": {
            "project": project,
            "contact_name": contact_name,
            "contact_phone": contact_phone,
            "footer_text": " | ".join(footer_parts),
        },
    }


def parse(text: str):
    data = parse_yuval_alon(text)
    if not data:
        return None

    items = []
    for raw_item in data.get("items", []):
        items.append(
            POItem(
                description=raw_item.get("description", "פריט לא זוהה"),
                sku=raw_item.get("sku") or "",
                quantity=raw_item.get("quantity", 1),
                unit_price=raw_item.get("unit_price", 0),
                line_total=raw_item.get("line_total", 0),
            )
        )

    header = {
        "customer_id": data.get("customer_id", ""),
        "customer_phone": data.get("customer_phone", ""),
        "customer_email": data.get("customer_email", ""),
        "delivery_address": data.get("delivery_address", ""),
        "po_number": data.get("po_number", ""),
        "po_date": data.get("po_date", ""),
        "subtotal": data.get("subtotal"),
        "vat": data.get("vat"),
        "total": data.get("total"),
        "project": data.get("extra", {}).get("project", ""),
        "contact_name": data.get("extra", {}).get("contact_name", ""),
        "contact_phone": data.get("extra", {}).get("contact_phone", ""),
        "payment_terms_days": None,
        "payment_terms_label": "",
    }
    return data.get("customer_name", ""), items, header
