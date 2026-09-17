"""הזמנת רכש של פלסן רא"ם (רכב אזרחי ממוגן, רמת דלתון) — מסמך חשבשבת ERP.

המבנה (טקסט pdfplumber, עברית הפוכה שורה-שורה):
- כותרת: 'קתעה 56590 : 'סמ שכר תנמזה' + 'ךיראת : 16/09/2026'
- שורת פריט אחת לכל שורה בטבלה, והמשך התיאור בשורה נפרדת מתחתיה:
    ףסונ ךיראת 20/09/2026 15,360.00 0 ח"ש 160.00 96.00 <תיאור הפוך> 1000058 1
    1 1.5*64 הריעב
- סיכומים בעמוד האחרון: סה"כ, מע"מ %, סך לתשלום בש"ח
- קניין: 'ךזבא ברימ ןינק םש'

עמוד 1 ועמוד 2 חוזרים על אותה כותרת — כל regex כותרתי תופס את המופע הראשון.
"""
from __future__ import annotations

import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws


# השם המדויק כפי שהלקוח רשום בחשבונית ירוקה (אומת מול ה-API לפי הח.פ,
# guid 4c4b7b0b). לא כמו שמופיע ב-PDF ("פלסן רא"ם...רכב אזרחי ממוגן") ולא
# כמו בעותק המקומי של ספר הלקוחות ("פלסאן ראמ") — ה-API הוא מקור האמת.
CUSTOMER_NAME = "פלסן רא״מ"
CUSTOMER_TAX_ID = "515057412"

_HEBREW_CHAR = re.compile(r"[֐-׿]")

_ITEM_LINE = re.compile(
    r"^ףסונ ךיראת\s+"          # "תאריך נוסף" — פותח כל שורת פריט בטקסט ההפוך
    r"(\d{2}/\d{2}/\d{4})\s+"   # ת. מבוקש
    r"([\d,]+\.\d{2})\s+"       # סה"כ שורה
    r"(\d+(?:\.\d+)?)\s+"       # % הנחה
    r'ח"ש\s+'                   # מטבע
    r"([\d,]+\.\d{2})\s+"       # מחיר ליחידה
    r"([\d,]+\.\d{2})\s+"       # כמות
    r"(.+?)\s+"                 # תיאור (הפוך)
    r"(\d{5,9})\s+"             # מק"ט
    r"(\d{1,3})\s*$"            # מס' שורה
)

_CONTINUATION_SKIP = re.compile(
    r"השרומ קסוע|ןסלפ|דוקימ|הופק|ממוחשב|ךותמ|כ\"הס|מ\"עמ|ןינק"
)


def _reverse_hebrew_tokens(value: str) -> str:
    """הופך רק אסימונים עבריים ומחזיר את סדר המילים — מספרים ולטינית לא נפגעים.

    ההיפוך הנאיבי של almogim הופך גם "1.5*64" ל-"46*5.1"; כאן מידות ומק"טים
    שמוטמעים בתיאור שורדים כמו שהם.
    """
    tokens = normalize_ws(value or "").split()
    restored = [token[::-1] if _HEBREW_CHAR.search(token) else token for token in tokens]
    return " ".join(reversed(restored)).strip()


def _amount(value: str) -> float:
    try:
        return float(str(value or "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def detect(raw_text: str) -> bool:
    haystack = raw_text or ""
    if CUSTOMER_TAX_ID not in haystack:
        return False
    return 'מ"אר ןסלפ' in haystack or 'פלסן רא"מ' in haystack or 'פלסן רא"ם' in haystack


def _extract_items(lines: list[str]) -> list[POItem]:
    items: list[POItem] = []
    seen_keys: set[tuple] = set()
    for index, line in enumerate(lines):
        match = _ITEM_LINE.match(line)
        if not match:
            continue

        description = _reverse_hebrew_tokens(match.group(6))
        # המשך התיאור יושב בשורה הבאה, אחרי ספרת "ת.מאושר" בודדת בתחילתה
        if index + 1 < len(lines):
            continuation = lines[index + 1]
            if not _ITEM_LINE.match(continuation) and not _CONTINUATION_SKIP.search(continuation):
                continuation = re.sub(r"^\d{1,3}\s+", "", continuation).strip()
                if continuation:
                    description = normalize_ws(f"{description} {_reverse_hebrew_tokens(continuation)}")

        item = POItem(
            sku=match.group(7),
            description=description,
            # לטבלת חשבשבת של רא"ם אין עמודת יחידה; הסחורה שלהם היא יריעות
            # במ"ר (גליל 1.5×64 = 96 מ"ר לשורה בהזמנה 56590), וההזמנה הראשונה
            # יצאה עם מדבקות "יח׳" בגלל ברירת המחדל. אפשר לשנות במסך הבדיקה.
            unit='מ"ר',
            quantity=_amount(match.group(5)),
            unit_price=_amount(match.group(4)),
            line_total=_amount(match.group(2)),
        )
        # שני העמודים חוזרים על הכותרת אבל לא על הפריטים; ליתר ביטחון מסננים
        # שורה זהה שחוזרת פעמיים לפי (מס' שורה, מק"ט, סה"כ)
        key = (match.group(8), item.sku, item.line_total)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        items.append(item)
    return items


def parse(text: str):
    if not detect(text):
        return None

    lines = [normalize_ws(line) for line in (text or "").splitlines() if normalize_ws(line)]
    full_text = "\n".join(lines)

    header = {
        "customer_id": CUSTOMER_TAX_ID,
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

    m = re.search(r"(\d{3,})\s*:\s*'סמ שכר תנמזה", full_text)
    if m:
        header["po_number"] = m.group(1)

    m = re.search(r"(\d{2}/\d{2}/\d{4})\s*:\s*ךיראת", full_text)
    if m:
        header["po_date"] = normalize_date(m.group(1))

    m = re.search(r"([\d,]+\.\d{2})\s*:\s*כ\"הס", full_text)
    if m:
        header["subtotal"] = _amount(m.group(1))

    m = re.search(r"([\d,]+\.\d{2})\s*:\s*מ\"עמ\s*%", full_text)
    if m:
        header["vat"] = _amount(m.group(1))

    m = re.search(r"([\d,]+\.\d{2})\s+ח\"שב םולשתל ךס", full_text)
    if m:
        header["total"] = _amount(m.group(1))

    m = re.search(r"([א-ת]+ [א-ת]+)\s+ןינק םש", full_text)
    if m:
        header["contact_name"] = _reverse_hebrew_tokens(m.group(1))

    # "כתובת: העבודה 2" ובשורה נפרדת "חיפה" — אתר האספקה של פלסן רא"ם
    m = re.search(r"(\d+)\s+הדובעה\s*:\s*תבותכ", full_text)
    if m:
        header["delivery_address"] = f"העבודה {m.group(1)}, חיפה" if "הפיח" in full_text else f"העבודה {m.group(1)}"

    items = _extract_items(lines)
    if not items:
        items = [POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="")]

    items_total = round(sum(item.line_total or 0 for item in items), 2)
    if not header["subtotal"] and items_total:
        header["subtotal"] = items_total
    if not header["vat"] and header["subtotal"]:
        header["vat"] = round(header["subtotal"] * 0.18, 2)
    if not header["total"] and header["subtotal"]:
        header["total"] = round(header["subtotal"] + header["vat"], 2)

    return CUSTOMER_NAME, items, header
