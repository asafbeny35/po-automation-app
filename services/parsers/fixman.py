"""הזמנת רכש של פיקסמן בנייה בע"מ (הזמנה 186/4492, 22.09.2026).

שלוש מלכודות במסמך הזה:

1. **גליף שבור**: הפונט של המסמך ממפה את האות נ' ל-(cid:170) בחילוץ טקסט —
   "הזמנה" יוצאת "הזמ(cid:170)ה". בלי נרמול, אף עוגן עברי לא נתפס.
2. **מק"ט שנשבר לשתי שורות**: העמודה צרה, והקוד ממשיך בשורה נפרדת
   ("--070410" ואז "013"), לפעמים דבוק למילה העברית האחרונה בתיאור
   ("ןגמ-STEPRO050").
3. **איש הקשר המודפס הוא אנחנו**: "איש קשר: בן יעקב, נייד 054-7720142" —
   הטלפון של אסף. אסור שיזלוג לאיש הקשר של הלקוח; המזמינה האמיתית מופיעה
   בתחתית ("הזמנה זו הופקה ע"י").
"""
from __future__ import annotations

import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws

# השם המדויק כפי שהלקוח רשום בחשבונית ירוקה (guid 645daaab, אומת מול ה-API)
CUSTOMER_NAME = "פיקסמן בנייה"
CUSTOMER_TAX_ID = "514946664"

OUR_PHONE = "054-7720142"

_HEBREW_CHAR = re.compile(r"[֐-׿]")
_CID_TOKEN = re.compile(r"\(cid:(\d+)\)")
_CID_MAP = {"170": "נ"}

# [סה"כ שורה] [מחיר, 3 ספרות] [כמות] 'חי [תיאור הפוך + מק"ט]
_ITEM_LINE = re.compile(
    r"^([\d,]+\.\d{2})\s+([\d,]+\.\d{3})\s+([\d,]+(?:\.\d+)?)\s+'חי\s+(.+)$"
)
_SKU_CONTINUATION = re.compile(r"^[A-Za-z0-9]{1,8}$")
_DIMENSIONS_TOKEN = re.compile(r"^([\d.]+)\*([\d.]+)$")


def _normalize_cids(text: str) -> str:
    """ממפה גליפים שבורים חזרה לאותיות. cid לא מוכר נשאר גלוי בכוונה —
    עדיף שאסף יראה (cid:184) בתיאור וידווח, מאשר אות שנעלמת בשקט."""
    return _CID_TOKEN.sub(lambda m: _CID_MAP.get(m.group(1), m.group(0)), text or "")


def _reverse_hebrew_tokens(value: str) -> str:
    """הופך אסימונים עבריים ואת סדר המילים; מספרים ולטינית לא נפגעים.

    אסימון מידות ("2.5*1.5") מתהפך סביב הכוכבית: pdfplumber מוציא את ריצת
    המידות בסדר חזותי, והמקור הוא "1.5*2.5" (פודסטים 1.5x2.5)."""
    tokens = normalize_ws(value or "").split()
    restored: list[str] = []
    for token in tokens:
        if _HEBREW_CHAR.search(token):
            restored.append(token[::-1])
            continue
        dims = _DIMENSIONS_TOKEN.match(token)
        if dims:
            restored.append(f"{dims.group(2)}*{dims.group(1)}")
            continue
        restored.append(token)
    return " ".join(reversed(restored)).strip()


def _amount(value: str) -> float:
    try:
        return float(str(value or "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def detect(raw_text: str) -> bool:
    text = _normalize_cids(raw_text or "")
    lowered = text.lower()
    return (
        CUSTOMER_TAX_ID in text
        or "fixman-ltd" in lowered
        or "ןמסקיפ" in text
        or "פיקסמן" in text
    )


def _split_desc_and_sku(rest: str) -> tuple[str, str]:
    """מפריד את המק"ט (ריצה לטינית/ספרתית בקצה) מהתיאור העברי ההפוך."""
    tokens = normalize_ws(rest).split()
    sku_parts: list[str] = []
    while tokens:
        tail = tokens[-1]
        if not _HEBREW_CHAR.search(tail) and re.fullmatch(r"[A-Za-z0-9-]+", tail) and not _DIMENSIONS_TOKEN.match(tail):
            sku_parts.insert(0, tokens.pop())
            continue
        # מק"ט שנדבק למילה העברית האחרונה: "ןגמ-STEPRO050"
        glued = re.match(r"^(.*?[֐-׿])-?([A-Za-z][A-Za-z0-9-]*)$", tail)
        if glued:
            tokens[-1] = glued.group(1)
            sku_parts.insert(0, glued.group(2))
        break
    description = _reverse_hebrew_tokens(" ".join(tokens))
    sku = "".join(sku_parts)
    return description, sku


def _clean_sku(value: str) -> str:
    return re.sub(r"-{2,}", "-", str(value or "")).strip("-")


def _extract_items(lines: list[str]) -> list[POItem]:
    items: list[POItem] = []
    for index, line in enumerate(lines):
        match = _ITEM_LINE.match(line)
        if not match:
            continue
        description, sku = _split_desc_and_sku(match.group(4))
        # המשך מק"ט בשורה הבאה (העמודה צרה): "--070410" ואז "013".
        # אחרי אותיות מחברים ישר (STEPSPE + 050 = STEPSPE050, כמו אחיו
        # STEPRO050); אחרי ספרות — עם מקף, שלא יידבקו לספרה אחת (070410-013).
        if index + 1 < len(lines) and _SKU_CONTINUATION.match(lines[index + 1]) and not _ITEM_LINE.match(lines[index + 1]):
            continuation = lines[index + 1]
            if not sku:
                sku = continuation
            elif sku.rstrip("-")[-1:].isdigit():
                sku = f"{sku}-{continuation}"
            else:
                sku = f"{sku}{continuation}"
        items.append(
            POItem(
                sku=_clean_sku(sku),
                description=description,
                unit="יח'",
                quantity=_amount(match.group(3)),
                unit_price=_amount(match.group(2)),
                line_total=_amount(match.group(1)),
            )
        )
    return items


def parse(text: str):
    text = _normalize_cids(text or "")
    if not detect(text):
        return None

    lines = [normalize_ws(line) for line in text.splitlines() if normalize_ws(line)]
    full_text = "\n".join(lines)

    header = {
        "customer_id": CUSTOMER_TAX_ID,
        "customer_email": "",
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

    m = re.search(r"(\d{2,4}/\d{3,6})\s+'סמ\s+ה?נמזה", full_text)
    if m:
        header["po_number"] = m.group(1)

    m = re.search(r"(\d{2}/\d{2}/\d{2,4})\s+\d{2}:\d{2}", full_text)
    if m:
        header["po_date"] = normalize_date(m.group(1))

    # כותרת: "רוקמ - <מס'> 'סמ הנמזה - <פרויקט הפוך> טקיורפ"
    m = re.search(r"'סמ\s+ה?נמזה\s+-\s+(.+?)\s+טקיורפ", full_text)
    if m:
        header["project"] = _reverse_hebrew_tokens(m.group(1))

    # כתובת האתר: שם הפרויקט הוא הרחוב; העיר מזוהה בנפרד כי עמודות המסמך
    # ממוזגות בחילוץ (הכתובת שלנו והאתר יושבים על אותה שורה חזותית)
    if header["project"]:
        city = "תל אביב" if "ביבא לת" in full_text else ""
        header["delivery_address"] = f"{header['project']}, {city}".strip(" ,") if city else header["project"]

    m = re.search(r"(\d+)\s*\+\s*ףטוש", full_text)
    if m:
        header["payment_terms_days"] = int(m.group(1))
        header["payment_terms_label"] = f"שוטף + {m.group(1)}"

    m = re.search(r"([\d,]+\.\d{2})\s*:ה?נמזה\s+כ\"הס", full_text)
    if m:
        header["subtotal"] = _amount(m.group(1))

    m = re.search(r"[\w.-]+@[\w.-]+\.\w+", full_text)
    if m:
        header["customer_email"] = m.group(0)

    # המזמינה האמיתית — "הזמנה זו הופקה ע"י"; איש הקשר המודפס הוא הטלפון שלנו
    m = re.search(r"([א-ת]+ [א-ת]+)\s*:\s*י\"ע\s+הקפוה", full_text)
    if m:
        header["contact_name"] = _reverse_hebrew_tokens(m.group(1))

    items = _extract_items(lines)
    if not items:
        items = [POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="")]

    items_total = round(sum(item.line_total or 0 for item in items), 2)
    if not header["subtotal"] and items_total:
        header["subtotal"] = items_total
    # "סה"כ הזמנה ... לא כולל מע"מ" — המע"מ תמיד נגזר
    header["vat"] = round(header["subtotal"] * 0.18, 2)
    header["total"] = round(header["subtotal"] + header["vat"], 2)

    return CUSTOMER_NAME, items, header
