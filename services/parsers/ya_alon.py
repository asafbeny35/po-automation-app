import re
from typing import Optional

from services.models import POItem
from services.parsers.common import normalize_date, normalize_po_number, normalize_ws


CUSTOMER_NAME = "י.א אלון בניה"
RAW_MARKERS = (
    "הינב ןולא א.י",
    "שכר תנמזה",
    "support@punct.co.il",
)


def _clean_text(text: str) -> str:
    cleaned = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", text or "")
    cleaned = cleaned.replace("\r", "\n").replace("\x00", " ")
    return cleaned


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
    restored = re.sub(r"(\d)\s*,\s*(\d)", r"\1,\2", restored)
    restored = re.sub(r"(למסירה)(?=[א-ת])", r"\1 ", restored)
    restored = re.sub(r"(לכבוד)(?=[א-ת])", r"\1 ", restored)
    restored = restored.replace("הגורן,34", "הגורן 34,")
    restored = restored.replace(" /", "/")
    return normalize_ws(restored)


def _restore_text(text: str) -> str:
    cleaned = _clean_text(text)
    if not any(marker in cleaned for marker in RAW_MARKERS):
        return cleaned
    restored_lines = [_restore_reversed_line(line) for line in cleaned.splitlines()]
    return "\n".join(line for line in restored_lines if normalize_ws(line))


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 9:
        digits = f"0{digits}"
    return digits


def _normalize_amount(value: str) -> float:
    token = normalize_ws(value).replace(",", "").replace(" ", "")
    token = token.replace("₪", "").replace('ש"ח', "").replace("שח", "")
    token = re.sub(r"[^\d.]", "", token)
    try:
        return float(token) if token else 0.0
    except Exception:
        return 0.0


def _find_first(pattern: str, text: str, flags=re.MULTILINE):
    match = re.search(pattern, text, flags)
    return normalize_ws(match.group(1)) if match else ""


def _extract_header(restored_text: str) -> dict:
    lines = [normalize_ws(line) for line in restored_text.splitlines() if normalize_ws(line)]
    header = {
        "customer_name": CUSTOMER_NAME,
        "customer_id": "",
        "customer_phone": "",
        "customer_email": "",
        "delivery_address": "",
        "po_number": "",
        "po_date": "",
        "subtotal": 0.0,
        "vat": 0.0,
        "total": 0.0,
        "project": "",
        "contact_name": "",
        "contact_phone": "",
        "payment_terms_days": None,
        "payment_terms_label": "",
        "extra": {},
    }

    top_line = next((line for line in lines if line.startswith("הזמנת רכש מס")), "")
    top_match = re.search(r"הזמנת רכש מס\s+([A-Za-z0-9/-]+)\s+\|\s+(.+)", top_line)
    if top_match:
        header["po_number"] = normalize_po_number(top_match.group(1))
        header["project"] = normalize_ws(top_match.group(2))

    invoice_line = next((line for line in lines if line.startswith("חשבונית על שם")), "")
    invoice_match = re.search(r'"([^"]+)"', invoice_line)
    if invoice_match:
        header["customer_name"] = normalize_ws(invoice_match.group(1))

    delivery_line = next((line for line in lines if line.startswith("רח'") or line.startswith("רחוב")), "")
    if delivery_line:
        delivery_line = delivery_line.replace("/ ", "/")
        header["delivery_address"] = delivery_line
        if header["project"]:
            header["delivery_address"] = f"{delivery_line}, {header['project']}"

    company_line = next((line for line in lines if line.startswith("כתובת למשלוח")), "")
    company_match = re.search(
        r"כתובת למשלוח\s+(0\d{8,9})\s+([א-ת\"׳'\s-]+?)\s+שם החברה\s+(.+?)\s+לכבוד",
        company_line,
    )
    if company_match:
        header["customer_phone"] = _normalize_phone(company_match.group(1))
        header["extra"]["site_contact_name"] = normalize_ws(company_match.group(2))
        header["extra"]["site_contact_phone"] = header["customer_phone"]
        header["customer_name"] = normalize_ws(company_match.group(3)) or header["customer_name"]

    alt_phone_line = next((line for line in lines if re.fullmatch(r"0\d{1,2}-\d{7}", line)), "")
    if alt_phone_line:
        header["extra"]["alternate_phone"] = _normalize_phone(alt_phone_line)

    ids_line = next((line for line in lines if line.startswith("תאריך הספקה")), "")
    ids_match = re.search(r"תאריך הספקה\s+([0-9./]+)\s+ח\.פ\s+([0-9]{9})\s+ח\.פ\s+([0-9]{9})", ids_line)
    if ids_match:
        header["po_date"] = normalize_date(ids_match.group(1).replace(".", "/"))
        header["customer_id"] = ids_match.group(2)
        header["extra"]["supplier_id"] = ids_match.group(3)

    contact_line = next((line for line in lines if line.startswith("איש קשר למסירה")), "")
    contact_match = re.search(
        r"איש קשר למסירה\s+(.+?)\s+שם המזמין\s+(.+?)\s+כתובת הספק\s+(.+)",
        contact_line,
    )
    if contact_match:
        header["contact_name"] = normalize_ws(contact_match.group(1))
        header["extra"]["buyer_name"] = normalize_ws(contact_match.group(2))
        header["extra"]["supplier_address"] = normalize_ws(contact_match.group(3))

    phones_line = next((line for line in lines if line.startswith("טלפון 0")), "")
    phone_matches = re.findall(r"טלפון\s+(0\d{8,9})", phones_line)
    if phone_matches:
        if len(phone_matches) >= 1 and not header["contact_phone"]:
            header["contact_phone"] = _normalize_phone(phone_matches[0])
        if len(phone_matches) >= 2:
            header["extra"]["buyer_phone"] = _normalize_phone(phone_matches[1])
        if len(phone_matches) >= 3:
            header["extra"]["supplier_phone"] = _normalize_phone(phone_matches[2])

    totals_line = next((line for line in lines if line.startswith("סה”כ פריטים")), "")
    subtotal_raw = _find_first(r"סכום לפני מע.?מ:\s*₪?\s*([0-9., ]+)", totals_line)
    vat_raw = _find_first(r"מע.?מ\s+[0-9.]+%:\s*₪?\s*([0-9., ]+)", totals_line)
    total_raw = _find_first(r"סה.?כ מחיר:\s*₪?\s*([0-9., ]+)", totals_line)
    header["subtotal"] = _normalize_amount(subtotal_raw)
    header["vat"] = _normalize_amount(vat_raw)
    header["total"] = _normalize_amount(total_raw)
    if not header["vat"] and header["subtotal"] and header["total"]:
        header["vat"] = round(header["total"] - header["subtotal"], 2)

    notes_line = next((line for line in lines if line.startswith("הערות:")), "")
    if notes_line:
        header["extra"]["order_notes"] = notes_line.replace("הערות:", "", 1).strip()

    footer_parts = []
    if header["customer_id"]:
        footer_parts.append(f"ח.פ / ע.מ: {header['customer_id']}")
    if header["po_number"]:
        footer_parts.append(f"הזמנת רכש {header['po_number']}")
    if header["project"]:
        footer_parts.append(f"פרויקט: {header['project']}")
    if header["delivery_address"]:
        footer_parts.append(f"כתובת לאספקה: {header['delivery_address']}")
    if header["contact_name"]:
        footer_parts.append(f"איש קשר: {header['contact_name']}")
    if header["contact_phone"]:
        footer_parts.append(f"טל': {header['contact_phone']}")
    header["extra"]["footer_text"] = " | ".join(footer_parts)

    return header


def _clean_description(value: str) -> str:
    description = normalize_ws(value)
    if description == "הובלה הובלה":
        return "הובלה"
    if " כיסוי " in description and " - " not in description:
        first, second = description.split(" כיסוי ", 1)
        second = f"כיסוי {second}".strip()
        if first.strip() and second and second != first.strip():
            return f"{first.strip()} - {second}"
    return description


def _extract_items(restored_text: str) -> list[dict]:
    items: list[dict] = []
    lines = [normalize_ws(line) for line in restored_text.splitlines() if normalize_ws(line)]

    for line in lines:
        if "₪" not in line or line.startswith("סה") or line.startswith("הערות:"):
            continue
        match = re.search(
            r"^(?P<description>.+?)\s+(?P<unit>יחידה|יחידות|יח'|מ\"ר|מ״ר)\s+"
            r"(?P<quantity>\d+(?:\.\d+)?)\s+"
            r"(?P<unit_price>[0-9., ]+)\s*₪\s+"
            r"(?P<discount>[0-9.]+%)\s+"
            r"(?P<line_total>[0-9., ]+)\s*₪$",
            line,
        )
        if not match:
            continue

        description = _clean_description(match.group("description"))
        items.append(
            {
                "description": description or "פריט לא זוהה",
                "sku": "",
                "quantity": _normalize_amount(match.group("quantity")),
                "unit_price": _normalize_amount(match.group("unit_price")),
                "line_total": _normalize_amount(match.group("line_total")),
                "unit": normalize_ws(match.group("unit")),
            }
        )

    return items


def parse_ya_alon(text: str) -> Optional[dict]:
    restored_text = _restore_text(text)
    if "י.א אלון בניה" not in restored_text or "הזמנת רכש מס" not in restored_text:
        return None

    header = _extract_header(restored_text)
    items = _extract_items(restored_text)
    if not items:
        items = [{
            "description": "פריט לא זוהה",
            "sku": "",
            "quantity": 1,
            "unit_price": 0,
            "line_total": 0,
            "unit": "",
        }]

    return {
        "customer_name": header["customer_name"] or CUSTOMER_NAME,
        "customer_id": header["customer_id"],
        "customer_phone": header["customer_phone"],
        "customer_email": header["customer_email"],
        "delivery_address": header["delivery_address"],
        "po_number": header["po_number"],
        "po_date": header["po_date"],
        "subtotal": header["subtotal"],
        "vat": header["vat"],
        "total": header["total"],
        "items": items,
        "extra": header["extra"],
        "project": header["project"],
        "contact_name": header["contact_name"],
        "contact_phone": header["contact_phone"],
        "payment_terms_days": header["payment_terms_days"],
        "payment_terms_label": header["payment_terms_label"],
    }


def parse(text: str):
    data = parse_ya_alon(text)
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
                unit=raw_item.get("unit") or "",
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
        "project": data.get("project", ""),
        "contact_name": data.get("contact_name", ""),
        "contact_phone": data.get("contact_phone", ""),
        "payment_terms_days": data.get("payment_terms_days"),
        "payment_terms_label": data.get("payment_terms_label", ""),
        "extra": data.get("extra", {}),
    }
    return data.get("customer_name", CUSTOMER_NAME), items, header
