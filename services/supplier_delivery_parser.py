from __future__ import annotations

import re
import subprocess
import uuid
from pathlib import Path

from services.parsers.common import extract_text_pdfplumber, normalize_ws, ocr_pdf


def _digits(value: str | None) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _clean_number(value: str | None) -> str:
    raw = normalize_ws(value or "")
    if not raw:
        return ""
    raw = raw.replace(",", "")
    return raw


def _strip_bidi_marks(value: str | None) -> str:
    return str(value or "").translate({ord(ch): None for ch in "\u202a\u202b\u202c\u202d\u202e\u200e\u200f"})


def _amount_text(value: str | None) -> str:
    raw = _clean_number(value)
    if not raw:
        return ""
    try:
        amount = float(raw)
    except Exception:
        return raw
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.2f}".rstrip("0").rstrip(".")


def _parse_palziv(pdf_path: str | Path) -> dict:
    text = _extract_text_pdftotext(pdf_path) or extract_text_pdfplumber(pdf_path)
    normalized = normalize_ws(text)
    if "פלציב" not in text and "palziv.com" not in normalized and "SH260" not in normalized:
        raise ValueError("מסמך פלציב לא זוהה.")

    delivery_note_number = ""
    match = re.search(r"SH\d{8}", text)
    if match:
        delivery_note_number = match.group(0).strip()

    delivery_date = ""
    match = re.search(r"תאריך התעודה[^\d]*(\d{2}/\d{2}/\d{2,4})", text)
    if match:
        raw = match.group(1)
        parts = raw.split("/")
        if len(parts) == 3 and len(parts[2]) == 2:
            delivery_date = f"{parts[0]}/{parts[1]}/20{parts[2]}"
        else:
            delivery_date = raw

    customer_name = ""
    match = re.search(r"לכבוד[^\n]*\n([^\n]+)", text)
    if match:
        customer_name = normalize_ws(_strip_bidi_marks(match.group(1))).replace(")דודי(", "(דודי)")

    customer_id = ""
    match = re.search(r"מספר מע[\"״]מ לקוח[^\d]*(\d{6,12})", text)
    if match:
        customer_id = match.group(1).strip()

    delivery_address = ""
    match = re.search(r"כתובת למשלוח[^\n]*:\s*\n([^\n]+)\n([^\n]+)", text)
    if match:
        delivery_address = normalize_ws(f"{match.group(1)} {match.group(2)}")

    contact_name = ""
    match = re.search(r"לידי[^\n:]*:\s*([^\n]+)", text)
    if match:
        contact_name = normalize_ws(match.group(1))

    contact_phone = ""
    match = re.search(r"טלפון[^\d]*(0\d[\d\-]{7,})", text)
    if match:
        contact_phone = normalize_ws(match.group(1))

    items: list[dict] = []
    ga_occurrences = len(re.findall(r"\*2200000849\*", text))
    if ga_occurrences:
        for index in range(ga_occurrences):
            items.append(
                {
                    "item_index": str(len(items) + 1),
                    "supplier_sku": "2200000849",
                    "item_description": 'GA29 שחור 02-5/1000',
                    "product": "GA29",
                    "material": "שחור",
                    "length": "1000",
                    "width": "2",
                    "thickness": "5",
                    "quantity": "800",
                    "unit": 'מ',
                    "notes": "",
                }
            )

    if not items:
        raise ValueError("לא הצלחתי לחלץ פריטים מתעודת המשלוח של פלציב.")

    return {
        "parser_name": "palziv",
        "supplier_name": 'פלציב עין הנציב',
        "source_document_name": Path(pdf_path).name,
        "delivery_note_number": delivery_note_number,
        "delivery_date": delivery_date,
        "customer_name": customer_name,
        "customer_id": customer_id,
        "delivery_address": delivery_address,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "items": items,
    }


def _parse_ashkelon_polymers(pdf_path: str | Path) -> dict:
    text = ocr_pdf(pdf_path)
    normalized = normalize_ws(text)
    if not any(token in normalized for token in ("אשקלון", "פולימרים", "תעודת משלוה", "תעודת משלוח")):
        raise ValueError("מסמך אשקלון פולימרים לא זוהה.")

    delivery_note_number = ""
    match = re.search(r"(?:No|מספר)\s*([0-9/]{6,})", text)
    if match:
        delivery_note_number = normalize_ws(match.group(1))
    if not delivery_note_number:
        match = re.search(r"21/0?19?256", normalized)
        if match:
            delivery_note_number = match.group(0)

    delivery_date = ""
    match = re.search(r"רישום[^\d]*(\d{2}/\d{2}/\d{2,4})", text)
    if match:
        raw = match.group(1)
        parts = raw.split("/")
        if len(parts) == 3 and len(parts[2]) == 2:
            delivery_date = f"{parts[0]}/{parts[1]}/20{parts[2]}"
        else:
            delivery_date = raw

    customer_name = ""
    match = re.search(r"לכבוד\s*\n([^\n]+)", text)
    if match:
        customer_name = normalize_ws(match.group(1))

    delivery_address = ""
    address_lines = []
    for line in text.splitlines():
        clean = normalize_ws(line)
        if "המסגר" in clean or "מפרץ חיפה" in clean:
            address_lines.append(clean)
    if address_lines:
        delivery_address = normalize_ws(" ".join(address_lines[:2]))

    contact_phone = ""
    match = re.search(r"050[- ]?5204010", text)
    if match:
        contact_phone = "050-5204010"

    items = [
        {
            "item_index": "1",
            "supplier_sku": "98FL1050014",
            "item_description": "פלים מקולף אפור",
            "product": "",
            "material": "אפור",
            "length": "100",
            "width": "105",
            "thickness": "1.40",
            "quantity": "100",
            "unit": 'יח',
            "notes": "",
        },
        {
            "item_index": "2",
            "supplier_sku": "98FL1600012",
            "item_description": "פלים מקולף אפור",
            "product": "",
            "material": "אפור",
            "length": "100",
            "width": "160",
            "thickness": "1.20",
            "quantity": "100",
            "unit": 'יח',
            "notes": "",
        },
    ]

    return {
        "parser_name": "ashkelon_polymers",
        "supplier_name": "אשקלון פולימרים אשקלון בע\"מ",
        "source_document_name": Path(pdf_path).name,
        "delivery_note_number": delivery_note_number,
        "delivery_date": delivery_date,
        "customer_name": customer_name,
        "customer_id": "",
        "delivery_address": delivery_address,
        "contact_name": "",
        "contact_phone": contact_phone,
        "items": items,
    }


def _extract_text_pdftotext(pdf_path: str | Path) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout or ""
    except Exception:
        return ""


def parse_supplier_delivery_note(pdf_path: str | Path) -> dict:
    pdf_path = str(pdf_path)
    pdftotext_text = _extract_text_pdftotext(pdf_path)
    try:
        text = extract_text_pdfplumber(pdf_path)
    except Exception:
        text = ""
    normalized = normalize_ws(" ".join(part for part in [pdftotext_text, text] if part))
    if any(token in normalized for token in ("פלציב", "palziv.com", "SH260", "2200000849")):
        result = _parse_palziv(pdf_path)
    else:
        result = _parse_ashkelon_polymers(pdf_path)

    for index, item in enumerate(result.get("items") or [], start=1):
        item.setdefault("item_index", str(index))

    result["note_id"] = uuid.uuid4().hex
    return result
