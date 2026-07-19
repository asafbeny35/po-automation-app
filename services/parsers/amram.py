import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_po_number, normalize_ws, sanitize_contact_pair


CUSTOMER_NAME = 'עמרם אברהם ביצועים בע"מ'


def _clean(value: str) -> str:
    return normalize_ws(re.sub(r"[\u200e\u200f\u202a-\u202e]", "", value or ""))


def _amount(value: str) -> float:
    token = normalize_ws(value or "").replace(",", "").replace("₪", "").replace('ש"ח', "")
    try:
        return float(token)
    except Exception:
        return 0.0


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    if not digits:
        return ""
    if len(digits) == 9 and digits.startswith(("4", "8")):
        digits = "0" + digits
    if len(digits) == 10:
        return f"{digits[:3]}-{digits[3:]}"
    return value.replace(".", "-")


def _reverse_words(value: str) -> str:
    tokens = [token for token in normalize_ws(value or "").split(" ") if token]
    converted: list[str] = []
    for token in reversed(tokens):
        if re.search(r"[א-ת]", token):
            converted.append(token[::-1])
        else:
            converted.append(token)
    return normalize_ws(" ".join(converted))


def _reverse_token(token: str) -> str:
    return token[::-1] if re.search(r"[א-ת]", token) else token


def _description_from_pdf_columns(pdf_path) -> str:
    """חילוץ עמודת 'תאור מוצר' לפי קואורדינטות — לשורות פריט שגולשות לכמה שורות.

    כשההערה ארוכה, pdfplumber מפצל את שורת הפריט: המספרים בשורה אחת והתיאור
    וההערה מתערבבים בשורות נפרדות. גבולות העמודה נגזרים מכותרות הטבלה עצמן.
    """
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            words = pdf.pages[0].extract_words()
    except Exception:
        return ""
    desc_header = [w for w in words if w["text"] in ("רואת", "רצומ")]
    note_header = [w for w in words if w["text"] == "הרעה"]
    sku_header = [w for w in words if "ט\"קמ" in w["text"] or 'ט"קמ' in w["text"]]
    if not desc_header or not sku_header:
        return ""
    header_bottom = max(w["bottom"] for w in desc_header)
    sku_left = min(w["x0"] for w in sku_header)
    note_left = min((w["x0"] for w in note_header), default=0) - 80
    stop_words = [w for w in words if w["text"] in ("ללוכ", "דוקרב")]
    stop_top = min((w["top"] for w in stop_words), default=10**9)

    # כל המילים ברצועת הערה+תיאור (משמאל למק"ט), מקובצות לשורות
    band_words = [
        w for w in words
        if w["top"] > header_bottom + 1 and w["bottom"] < stop_top
        and note_left <= w["x0"] and w["x1"] <= sku_left - 2
    ]
    if not band_words:
        return ""
    lines: dict[int, list[dict]] = {}
    for w in band_words:
        lines.setdefault(round(w["top"] / 4), []).append(w)

    # הגבול בין עמודת ההערה לעמודת התיאור = המרווח האופקי הגדול ביותר
    # בשורה העמוסה ביותר (העמודות מופרדות בפער של ~10px, מילים בתוך עמודה ב-2-3px)
    busiest = max(lines.values(), key=len)
    ordered = sorted(busiest, key=lambda w: w["x0"])
    boundary = None
    best_gap = 6.0
    for prev_word, next_word in zip(ordered, ordered[1:]):
        gap = next_word["x0"] - prev_word["x1"]
        if gap > best_gap:
            best_gap = gap
            boundary = (prev_word["x1"] + next_word["x0"]) / 2
    parts: list[str] = []
    for key in sorted(lines):
        row = sorted(lines[key], key=lambda w: -w["x0"])
        kept = [w for w in row if boundary is None or (w["x0"] + w["x1"]) / 2 > boundary]
        if kept:
            parts.append(" ".join(_reverse_token(w["text"]) for w in kept))
    return normalize_ws(" ".join(parts))


def parse(text: str, pdf_path=None):
    if "םרמע" not in text and "office@amramb.co.il" not in text and "עמרם" not in text:
        return None

    lines = [_clean(line) for line in text.splitlines() if _clean(line)]
    flat = "\n".join(lines)

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

    email_match = re.search(r"e-mail:\s*([^\s]+@[^\s]+)", flat, re.IGNORECASE)
    if email_match:
        header["customer_email"] = email_match.group(1)

    id_match = re.search(r"(\d{9})\s*:\s*השרומ קסוע", flat)
    if id_match:
        header["customer_id"] = id_match.group(1)

    phone_match = re.search(r"([0-9.\-]+)\s*:\s*סקפ\s*,\s*([0-9.\-]+)\s*:\s*ןופלט", flat)
    if phone_match:
        header["customer_phone"] = _normalize_phone(phone_match.group(2))

    po_match = re.search(r"(PO\d+)\s+רפסמ שכר תנמזה", flat)
    if po_match:
        header["po_number"] = normalize_po_number(po_match.group(1))

    date_match = re.search(r"(\d{2}/\d{2}/\d{2})\s*:\s*הנמזה ךיראת", flat)
    if date_match:
        header["po_date"] = normalize_date(date_match.group(1))

    project_match = re.search(r"(.+?)\s*:\s*טקיורפ", flat)
    if project_match:
        header["project"] = _reverse_words(project_match.group(1))

    delivery_line = ""
    for index, line in enumerate(lines):
        if "ליטסקט תונורתפ בקעי ןב" not in line:
            continue
        cleaned_line = re.sub(r"^\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}\s*:\s*הספדה ךיראת\s*", "", line)
        cleaned_line = cleaned_line.replace("ליטסקט תונורתפ בקעי ןב", "").strip(" ,")
        if cleaned_line:
            delivery_line = _reverse_words(cleaned_line)

        contact_line = lines[index + 1] if index + 1 < len(lines) else ""
        phone_line = lines[index + 2] if index + 2 < len(lines) else ""
        if ":רשק שיא" in contact_line:
            header["contact_name"] = _reverse_words(contact_line.split(":רשק שיא", 1)[0].strip())
        phone_match = re.search(r"([0-9.\-]+)\s*:\s*'לט", phone_line)
        if phone_match:
            header["contact_phone"] = _normalize_phone(phone_match.group(1))
        break

    header["delivery_address"] = delivery_line or header["project"]

    item = POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="")
    item_match = re.search(
        r"([0-9,]+\.\d{2})\s+\d{2}/\d{2}/\d{2}\s+ח\"ש\s+([0-9,]+\.\d{2})\s+'חי\s+([0-9,]+\.\d{2})\s+(.+?)\s+(\d{10})\s+1",
        flat,
    )
    if item_match:
        line_total = _amount(item_match.group(1))
        unit_price = _amount(item_match.group(2))
        quantity = _amount(item_match.group(3))
        description = _reverse_words(item_match.group(4))
        sku = item_match.group(5)
        item = POItem(
            sku=sku,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
        )
        header["subtotal"] = line_total
    else:
        # שורת פריט מפוצלת: כשההערה ארוכה, המספרים נשארים לבד בשורה
        # ('790.00 16/07/26 ח"ש 79.00 יח' 10.00 8900040154 1') והתיאור בשורות נפרדות
        numbers_match = re.search(
            r"([0-9,]+\.\d{2})\s+\d{2}/\d{2}/\d{2}\s+ח\"ש\s+([0-9,]+\.\d{2})\s+'חי\s+([0-9,]+\.\d{2})\s+(\d{10})\s+1\b",
            flat,
        )
        if numbers_match:
            line_total = _amount(numbers_match.group(1))
            unit_price = _amount(numbers_match.group(2))
            quantity = _amount(numbers_match.group(3))
            sku = numbers_match.group(4)
            description = _description_from_pdf_columns(pdf_path) if pdf_path else ""
            item = POItem(
                sku=sku,
                description=description or "פריט לא זוהה",
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
            header["subtotal"] = line_total

    subtotal_match = re.search(r"([0-9,]+\.\d{2})\s+ללוכ ריחמ", flat)
    if subtotal_match:
        header["subtotal"] = _amount(subtotal_match.group(1))

    vat_match = re.search(r"([0-9,]+\.\d{2})\s+\(18\.00%\)\s+מ\"עמ", flat)
    if vat_match:
        header["vat"] = _amount(vat_match.group(1))

    total_match = re.search(r"ח\"ש\s+([0-9,]+\.\d{2})\s+ריחמ כ\"הס", flat)
    if total_match:
        header["total"] = _amount(total_match.group(1))

    terms_match = re.search(r"(\d+)(?=ש\s*:\s*םולשת יאנת)", flat)
    if terms_match:
        header["payment_terms_days"] = int(terms_match.group(1))
        header["payment_terms_label"] = f"שוטף + {terms_match.group(1)}"

    contact_name, contact_phone = sanitize_contact_pair(
        header.get("contact_name", ""),
        header.get("contact_phone", ""),
        customer_phone=header.get("customer_phone", ""),
    )
    header["contact_name"] = contact_name
    header["contact_phone"] = contact_phone

    return CUSTOMER_NAME, [item], header
