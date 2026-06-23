import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws, sanitize_contact_pair


CUSTOMER_NAME = 'אלמוגים בניה והשקעות בע"מ'


def _clean_line(value: str) -> str:
    value = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", value or "")
    value = re.sub(r"\s+", " ", value).strip()
    return normalize_ws(value)


def _amount(value: str) -> float:
    try:
        return float((value or "").replace(",", "").strip())
    except Exception:
        return 0.0


def _reverse_words(value: str) -> str:
    words = [part[::-1] for part in normalize_ws(value).split()]
    return " ".join(reversed(words)).strip()


def _extract_header(lines: list[str]) -> dict:
    full_text = "\n".join(lines)
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
    }

    m = re.search(r"(\d{9})\s*:\s*השרומ קסוע", full_text)
    if m:
        header["customer_id"] = m.group(1)

    m = re.search(r"([0-9]{2,3}-[0-9]{7})\s*:\s*ןופלט", full_text)
    if m:
        header["customer_phone"] = m.group(1)

    m = re.search(r"(PO\d+)\s+רפסמ שכר תנמזה", full_text)
    if m:
        header["po_number"] = m.group(1)

    m = re.search(r"(\d{2}/\d{2}/\d{2})\s*:\s*הנמזה ךיראת", full_text)
    if m:
        header["po_date"] = normalize_date(m.group(1))

    m = re.search(r"(.+?)\s*:\s*טקיורפ", full_text)
    if m:
        header["project"] = _reverse_words(m.group(1))

    m = re.search(r"(\d+)\s*ש\s*:\s*םולשת יאנת", full_text)
    if m:
        header["payment_terms_days"] = int(m.group(1))
        header["payment_terms_label"] = f"שוטף + {m.group(1)}"

    m = re.search(r"([\d,]+\.\d{2})\s+ללוכ ריחמ", full_text)
    if m:
        header["subtotal"] = _amount(m.group(1))

    m = re.search(r"([\d,]+\.\d{2})\s+\(18\.00%\)\s+מ\"עמ", full_text)
    if m:
        header["vat"] = _amount(m.group(1))

    m = re.search(r"ח\"ש\s+([\d,]+\.\d{2})\s+ריחמ כ\"הס", full_text)
    if m:
        header["total"] = _amount(m.group(1))

    return header


def _extract_delivery_and_contact(lines: list[str], customer_phone: str) -> tuple[str, str, str]:
    delivery_address = ""
    contact_name = ""
    contact_phone = ""

    for index, line in enumerate(lines):
        if "השמ תירק תובוחר" not in line:
            continue

        delivery_address = "רחובות קרית משה"
        if index + 1 < len(lines) and "םירופיכה םוי בוחר דיל" in lines[index + 1]:
            delivery_address += ", ליד רחוב יום הכיפורים"

        for candidate in lines[index + 2:index + 5]:
            m = re.search(r"(05\d{8})\s*-\s*([א-ת\"'׳\-]+)", candidate)
            if not m:
                continue
            phone = m.group(1)
            name = m.group(2)[::-1]
            clean_name, clean_phone = sanitize_contact_pair(name, phone, customer_phone=customer_phone)
            if clean_name or clean_phone:
                contact_name = clean_name
                contact_phone = clean_phone
                break
        break

    return delivery_address, contact_name, contact_phone


def _extract_item(lines: list[str]) -> POItem:
    for line in lines:
        if "356640153" not in line or "QUIETPIPE" not in line:
            continue

        m = re.search(
            r"([\d,]+\.\d{2})\s+ח\"ש\s+([\d,]+\.\d{2})\s+ר'מ\s+([\d,]+\.\d{2})\s+ר'מ\s+([\d,]+\.\d{2})\s+(\d{2}/\d{2}/\d{2})\s+QUIETPIPE\s*-\s*([א-ת\"'׳\-\s]+)\s+(\d{6,12})\s+\d+",
            line,
        )
        if not m:
            continue

        hebrew_part = _reverse_words(m.group(6))
        description = normalize_ws(f"{hebrew_part} QUIETPIPE").strip()

        return POItem(
            sku=m.group(7),
            description=description,
            quantity=_amount(m.group(4)),
            unit_price=_amount(m.group(2)),
            line_total=_amount(m.group(1)),
        )

    return POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="")


def parse(text: str):
    if ("גומלא" not in text and "אלמוג" not in text) or ("רפסמ שכר תנמזה" not in text and "הזמנת רכש" not in text):
        return None

    lines = [_clean_line(line) for line in (text or "").splitlines() if _clean_line(line)]
    header = _extract_header(lines)
    delivery_address, contact_name, contact_phone = _extract_delivery_and_contact(lines, header["customer_phone"])
    header["delivery_address"] = delivery_address
    header["contact_name"] = contact_name
    header["contact_phone"] = contact_phone

    item = _extract_item(lines)
    if not header["subtotal"] and item.line_total:
        header["subtotal"] = item.line_total
    if not header["vat"] and header["subtotal"]:
        header["vat"] = round(header["subtotal"] * 0.18, 2)
    if not header["total"] and header["subtotal"]:
        header["total"] = round(header["subtotal"] + header["vat"], 2)

    return CUSTOMER_NAME, [item], header
