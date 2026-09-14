import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws, sanitize_contact_pair


# השם כפי שהוא רשום בחשבונית ירוקה ובכל 5 ההזמנות הקודמות. הערך הקודם
# ("אלמוגים בניה והשקעות") הוא חברה שלא קיימת במאגר — בפיינליז הוא ניצל
# בזכות חיפוש לפי ח.פ, אבל המשתמש ראה שם לקוח שגוי לפני האישור.
CUSTOMER_NAME = "אלמוג ב.ז בנייה והשקעות בעמ"


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
            # ההזמנה כותבת "עיאד 0547957596" בלי מקף מפריד, והדרישה למקף
            # השאירה כל הזמנה בלי איש קשר לתעודת המשלוח.
            m = re.search(r"(05\d{8})\s*[-\s]\s*([א-ת\"'׳]+)", candidate)
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


_DATE_TOKEN = re.compile(r"^\d{2}/\d{2}/\d{2}$")
_AMOUNT_TOKEN = re.compile(r"^[\d,]+\.\d{2}$")
_SKU_TOKEN = re.compile(r"^\d{6,12}$")
_LATIN_CHAR = re.compile(r"[A-Za-z0-9]")
_HEBREW_CHAR = re.compile(r"[֐-׿]")
_MIRRORED_PUNCTUATION = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{"}


def _logical_text_from_visual(words: list[tuple[float, float, str]]) -> str:
    """סדר לוגי מתוך מילים שמוינו ימין→שמאל בעמוד.

    חילוץ טקסט מ-PDF עברי מחזיר את הסדר החזותי, ובו ריצה לטינית מוטמעת
    ("QUIETPIPE (2*1") מופיעה הפוכה ביחס לשאר השורה והסוגריים משוקפים.
    כאן מחזירים כל ריצה לטינית לסדרה, משקפים פיסוק נייטרלי, ומאחים מילים
    שה-bidi פיצל — שם רווח מזערי בין התיבות מסגיר שהן מילה אחת.
    """
    ordered: list[tuple[float, float, str]] = []
    latin_run: list[tuple[float, float, str]] = []

    def flush_latin() -> None:
        nonlocal latin_run
        if latin_run:
            ordered.extend(reversed(latin_run))
            latin_run = []

    for x0, x1, token in words:
        if _LATIN_CHAR.search(token) and not _HEBREW_CHAR.search(token):
            latin_run.append((x0, x1, token))
            continue
        flush_latin()
        if not _HEBREW_CHAR.search(token):
            token = "".join(_MIRRORED_PUNCTUATION.get(char, char) for char in reversed(token))
        ordered.append((x0, x1, token))
    flush_latin()

    parts: list[str] = []
    for index, (x0, x1, token) in enumerate(ordered):
        if index:
            previous_x0, previous_x1, _ = ordered[index - 1]
            gap = min(abs(x0 - previous_x1), abs(previous_x0 - x1))
            parts.append("" if gap < 1.2 else " ")
        parts.append(token)
    return normalize_ws("".join(parts))


def _visual_lines(pdf_path) -> list[list[tuple]]:
    import fitz

    document = fitz.open(str(pdf_path))
    try:
        words = document.load_page(0).get_text("words")
    finally:
        document.close()

    lines: list[list[tuple]] = []
    for word in sorted(words, key=lambda item: item[1]):
        for line in lines:
            if abs(line[0][1] - word[1]) <= 3.0:
                line.append(word)
                break
        else:
            lines.append([word])
    return [sorted(line, key=lambda item: -item[0]) for line in lines]


def _item_from_visual_line(line: list[tuple]) -> POItem | None:
    """שורת פריט: [מס' שורה][מק"ט][תיאור][ת. אספקה][כמות][יח'][יתרה][יח'][מחיר][מטבע][סה"כ]."""
    tokens = [word[4] for word in line]
    if len(tokens) < 8 or not tokens[0].isdigit() or len(tokens[0]) > 3:
        return None
    if not _SKU_TOKEN.match(tokens[1]):
        return None
    date_index = next((index for index, token in enumerate(tokens) if _DATE_TOKEN.match(token)), None)
    if date_index is None or date_index < 3:
        return None

    tail = tokens[date_index + 1:]
    amounts = [_amount(token) for token in tail if _AMOUNT_TOKEN.match(token)]
    if len(amounts) < 3:
        return None

    # היחידה ("מ'ר") מגיעה כתווים נפרדים ומוצמדים; בסדר ימין→שמאל הם כבר
    # קריאים, ולכן משרשרים כמות שהם במקום להפוך תו בודד.
    unit_chars: list[str] = []
    for word in line[date_index + 1:]:
        token = word[4]
        if _AMOUNT_TOKEN.match(token):
            if unit_chars:
                break
            continue
        if _HEBREW_CHAR.search(token) or token in {"'", '"', "׳", "״"}:
            unit_chars.append(token)
        elif unit_chars:
            break
    unit = "".join(unit_chars)

    description = _logical_text_from_visual(
        [(word[0], word[2], word[4]) for word in line[2:date_index]]
    )
    # הסדר בזנב (ימין→שמאל): כמות, יתרה לאספקה, מחיר ליחידה, סה"כ שורה
    quantity, unit_price, line_total = amounts[0], amounts[-2], amounts[-1]
    return POItem(
        sku=tokens[1],
        description=description,
        unit=unit,
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
    )


def _extract_items(lines: list[str], pdf_path=None) -> list[POItem]:
    """כל שורות הפריטים. הגרסה הקודמת נעלה מק"ט יחיד ודרשה ש-QUIETPIPE יהיה
    מוקף ברווחים; כשהספק הוסיף לתיאור את מידות הגליל — (2*1 מ') — ההתאמה
    נכשלה וכל הזמנה חזרה עם "פריט לא זוהה"."""
    items: list[POItem] = []
    if pdf_path:
        try:
            for line in _visual_lines(pdf_path):
                item = _item_from_visual_line(line)
                if item and item.line_total:
                    items.append(item)
        except Exception:
            items = []
    if items:
        return items

    # נפילה לאחור על הטקסט בלבד (סריקות בלי שכבת טקסט מסודרת)
    for line in lines:
        match = re.search(
            r"([\d,]+\.\d{2})\s+ח\"ש\s+([\d,]+\.\d{2})\s+(\S+)\s+([\d,]+\.\d{2})\s+\S+\s+"
            r"([\d,]+\.\d{2})\s+(\d{2}/\d{2}/\d{2})\s+(.+?)\s+(\d{6,12})\s+\d+\s*$",
            line,
        )
        if not match:
            continue
        items.append(
            POItem(
                sku=match.group(8),
                description=_reverse_words(match.group(7)),
                unit=match.group(3)[::-1],
                quantity=_amount(match.group(5)),
                unit_price=_amount(match.group(2)),
                line_total=_amount(match.group(1)),
            )
        )
    if items:
        return items
    return [POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="")]


def parse(text: str, pdf_path=None):
    if ("גומלא" not in text and "אלמוג" not in text) or ("רפסמ שכר תנמזה" not in text and "הזמנת רכש" not in text):
        return None

    lines = [_clean_line(line) for line in (text or "").splitlines() if _clean_line(line)]
    header = _extract_header(lines)
    delivery_address, contact_name, contact_phone = _extract_delivery_and_contact(lines, header["customer_phone"])
    header["delivery_address"] = delivery_address
    header["contact_name"] = contact_name
    header["contact_phone"] = contact_phone

    items = _extract_items(lines, pdf_path=pdf_path)
    items_total = round(sum(item.line_total or 0 for item in items), 2)
    if not header["subtotal"] and items_total:
        header["subtotal"] = items_total
    if not header["vat"] and header["subtotal"]:
        header["vat"] = round(header["subtotal"] * 0.18, 2)
    if not header["total"] and header["subtotal"]:
        header["total"] = round(header["subtotal"] + header["vat"], 2)

    return CUSTOMER_NAME, items, header
