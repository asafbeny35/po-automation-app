"""הזמנת רכש של רם אדרת הנדסה אזרחית בע"מ (פורטל PO<שנה><רץ>, למשל PO26006887).

שתי מלכודות במסמך הזה:

1. **היפוך תווים גורף הופך מספרים**: pdfplumber מוציא את הטקסט בסדר חזותי הפוך,
   והפרסר הקודם הפך כל שורה עם ``[::-1]`` — מה שהפך גם ספרות (מגרש 309 יצא 903,
   מתחם 67863 יצא 36876). הפתרון: היפוך מודע-אסימונים ששומר מספרים ולטינית.
2. **שורת הפריט משלבת מידות בתוך התיאור**: "מידות - נטו גובה 207 רוחב" יושבות
   בין הכמות לתיאור, והרגקס הנוקשה הקודם נשבר עליהן והחזיר "פריט לא זוהה".
   הפתרון: עיגון משמאל (סה"כ → מחיר → כמות) ושליפת המק"ט/תיאור מהשארית.
"""
from __future__ import annotations

import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws, sanitize_contact_pair

# השם והח"פ המדויקים כפי שהלקוח רשום בחשבונית ירוקה (guid f0b9cdec, אומת מול ה-API)
CUSTOMER_NAME = 'רם אדרת הנדסה אזרחית בע"מ'
CUSTOMER_TAX_ID = "512947185"

# הטלפון שלנו (בן יעקב) — אסור שיזלוג לאיש הקשר של הלקוח
OUR_PHONE_DIGITS = "0547720142"

_HEBREW_CHAR = re.compile(r"[֐-׿]")
_ZERO_WIDTH = re.compile(r"[​-‏‪-‮⁦-⁩]")

# ריצות אחידות להיפוך מודע-בידי: עברית / לטינית / מספר (עם מפרידים פנימיים) /
# רווח / שאר. מספר נשאר אטומי ("24/09/26", "3,900.00", "309") כדי שהיפוך הסדר
# לא יהפוך את ספרותיו — זו בדיוק התקלה שהפכה מגרש 309 ל-903.
_RUN_RE = re.compile(r"[֐-׿]+|[A-Za-z]+|\d+(?:[.,/:]\d+)*|\s+|[^֐-׿A-Za-z\d\s]+")

# [סה"כ] ח"ש [מחיר יחידה] 'חי [כמות] 'חי [כמות אספקה] [תיאור+מידות] [מק"ט] [שורה]
_ITEM_LINE = re.compile(
    r'^([\d,]+\.\d{2})\s+ח"ש\s+([\d,]+\.\d{2})\s+\'חי\s+([\d,]+\.\d{2})\s+\'חי\s+'
    r"([\d,]+\.\d{2})\s+(.+?)\s+(\d{8,})\s+\d+\s*$"
)

# שורות סיכום/שדה שאסור לצרף כהמשך תיאור הפריט
_STOP_TOKENS = ("מחיר", "ריחמ", 'מע"מ', 'מ"עמ', "כולל", "ללוכ", "תשלום", "םולשת", "פרויקט", "טקיורפ")


def _amount(value: str) -> float:
    try:
        return float(str(value or "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _reverse_hebrew_tokens(value: str) -> str:
    """הופך את הטקסט מסדר חזותי לסדר לוגי ברמת הריצה: הופך את סדר הריצות והופך
    את אותיות הריצות העבריות; ריצות מספר/לטינית נשארות פנימית כמות שהן, כך
    שספרות דבוקות לעברית (מתחם–309, ר-130) לא מתהפכות."""
    runs = _RUN_RE.findall(value or "")
    restored = [run[::-1] if _HEBREW_CHAR.search(run) else run for run in reversed(runs)]
    return normalize_ws("".join(restored))


def detect(raw_text: str) -> bool:
    text = _ZERO_WIDTH.sub("", raw_text or "")
    return (
        "רם אדרת" in text
        or "תרדא םר" in text
        or CUSTOMER_TAX_ID in text
        or "ram-aderet" in text.lower()
    )


def _extract_item(lines: list[str]) -> POItem | None:
    for index, line in enumerate(lines):
        match = _ITEM_LINE.match(line)
        if not match:
            continue
        line_total = _amount(match.group(1))
        unit_price = _amount(match.group(2))
        quantity = _amount(match.group(3))
        sku = match.group(6)
        # התיאור: השארית (תיאור + מידות) הפוכה חזותית; המשך אפשרי בשורה הבאה
        desc_visual = match.group(5)
        parts = [_reverse_hebrew_tokens(desc_visual)]
        if index + 1 < len(lines):
            nxt = lines[index + 1]
            if nxt and not _ITEM_LINE.match(nxt) and ":" not in nxt and not any(tok in nxt for tok in _STOP_TOKENS):
                parts.append(_reverse_hebrew_tokens(nxt))
        description = normalize_ws(" ".join(p for p in parts if p))
        # מנקים את חותמת "-אספקה DD/MM/YY" שדבוקה בתוך התיאור (תאריך האספקה כבר בכותרת)
        description = normalize_ws(re.sub(r"-?אספקה\s+\d{2}/\d{2}/\d{2}", "", description))
        return POItem(
            sku=sku,
            description=description or "פריט לא זוהה",
            unit="יח'",
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
        )
    return None


def parse(text: str):
    text = _ZERO_WIDTH.sub("", text or "")
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

    # מספר הזמנה — לטיני, מופיע כמות שהוא
    m = re.search(r"\b(PO\d+)\b", full_text)
    if m:
        header["po_number"] = m.group(1)

    m = re.search(r"(\d{2}/\d{2}/\d{2})\s*:\s*הנמזה ךיראת", full_text)
    if m:
        header["po_date"] = normalize_date(m.group(1))

    m = re.search(r"(\d+)ש\s*:\s*םולשת יאנת", full_text)
    if m:
        header["payment_terms_days"] = int(m.group(1))
        header["payment_terms_label"] = f"שוטף + {m.group(1)}"

    m = re.search(r'([\d.,]+)\s+\(18\.00%\)\s+מ"עמ', full_text)
    if m:
        header["vat"] = _amount(m.group(1))

    m = re.search(r'ח"ש\s+([\d.,]+)\s+ריחמ כ"הס', full_text)
    if m:
        header["total"] = _amount(m.group(1))

    # סכום ביניים: "מחיר כולל 3,900.00" (בסדר חזותי) — עוגן אמין לפני חישוב מהפריט
    m = re.search(r"([\d.,]+)\s+ללוכ ריחמ", full_text)
    if m:
        header["subtotal"] = _amount(m.group(1))

    # מייל לחשבוניות (invoices@) עדיף על office@ — לשם נשלחת חשבונית המס
    emails = re.findall(r"[\w.-]+@[\w.-]+\.\w+", full_text)
    header["customer_email"] = next((e for e in emails if e.lower().startswith("invoices@")), emails[0] if emails else "")

    # פרויקט: "... :טקיורפ" (הכל בסדר חזותי הפוך)
    m = re.search(r"(.+?)\s*:\s*טקיורפ", full_text)
    if m:
        header["project"] = _reverse_hebrew_tokens(m.group(1))

    # כתובת האספקה — השורה שמכילה את שם הספק שלנו; החלק שלפניו הוא כתובת האתר,
    # אחרי הסרת חותמת "תאריך הדפסה" שממוזגת לאותה שורה חזותית
    for line in lines:
        if "ליטסקט תונורתפ בקעי ןב" not in line:
            continue
        address_visual = line.split("ליטסקט תונורתפ בקעי ןב", 1)[0]
        address_visual = re.sub(r"\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}\s*:\s*הספדה ךיראת", "", address_visual)
        header["delivery_address"] = _reverse_hebrew_tokens(address_visual)
        break

    # איש הקשר משתנה מהזמנה להזמנה ומופיע כ"טלפון (שם)" — למשל
    # "/054-7300990 (לצרה)" ⇐ הרצל, 054-7300990. חמוטל שהופיע קודם *לא* היה
    # במסמך אלא נשלף מכרטיס הלקוח ב-GreenInvoice כשהפרסר החזיר איש קשר ריק.
    m = re.search(r"(0\d{1,2}-?\d{6,7})\s*\(([^)]+)\)", full_text)
    if m and m.group(1).replace("-", "") != OUR_PHONE_DIGITS:
        header["contact_phone"] = m.group(1)
        header["contact_name"] = _reverse_hebrew_tokens(m.group(2))

    item = _extract_item(lines)
    items = [item] if item else [POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="", unit="יח'")]

    if item and not header["subtotal"]:
        header["subtotal"] = item.line_total
    if not header["total"] and header["subtotal"]:
        header["vat"] = header["vat"] or round(header["subtotal"] * 0.18, 2)
        header["total"] = round(header["subtotal"] + header["vat"], 2)

    contact_name, contact_phone = sanitize_contact_pair(
        header.get("contact_name", ""),
        header.get("contact_phone", ""),
        customer_phone=header.get("customer_phone", ""),
    )
    header["contact_name"] = contact_name
    header["contact_phone"] = contact_phone

    return CUSTOMER_NAME, items, header
