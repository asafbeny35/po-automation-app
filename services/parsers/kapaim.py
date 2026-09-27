"""הזמנת רכש של כפיים בנייה (פריהד סגל פיתוח נדל"ן בע"מ, הזמנה PO26001915).

אותו פורטל של רם אדרת ("Print Purchase Order - PO..."), עם אותן מלכודות:
pdfplumber מוציא סדר חזותי הפוך, וספרות דבוקות לעברית מתהפכות בהיפוך גורף
(181.5*33 היה יוצא 33*181.5). ההבדלים מהלייאאוט של רם אדרת: המטבע ILS ולא
ח"ש בשורת הפריט, יש כמה שורות פריט, ומופיע "מנהל פרויקט" שמזוהה עם איש הקשר
שבבלוק הכתובת ("טלפון: דוד- 050-9033833").

שם המסמך הוא השם המשפטי (פריהד סגל); בחשבונית ירוקה הלקוח רשום "כפיים בנייה"
(guid b650414d, כרטיס בלי ח"פ) — השם חייב להתאים כדי שהסנכרון ימצא אותו.
"""
from __future__ import annotations

import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws, sanitize_contact_pair

CUSTOMER_NAME = "כפיים בנייה"
CUSTOMER_TAX_ID = "514547918"

# הטלפון שלנו (בן יעקב) — מודפס במסמך כאיש הקשר "אסף" ואסור שיזלוג ללקוח
OUR_PHONE_DIGITS = "0547720142"

_HEBREW_CHAR = re.compile(r"[֐-׿]")
_ZERO_WIDTH = re.compile(r"[​-‏‪-‮⁦-⁩]")

# ריצות אחידות להיפוך מודע-בידי — מספר נשאר אטומי (181.5, 24/09/26, 1,126.00)
_RUN_RE = re.compile(r"[֐-׿]+|[A-Za-z]+|\d+(?:[.,/:]\d+)*|\s+|[^֐-׿A-Za-z\d\s]+")

# [סה"כ] ILS [מחיר יחידה] 'חי [כמות] [תיאור הפוך] [מק"ט ספרתי-מקף] [שורה]
_ITEM_LINE = re.compile(
    r"^([\d,]+\.\d{2})\s+ILS\s+([\d,]+\.\d{2})\s+'חי\s+([\d,]+\.\d{2})\s+(.+?)\s+(\d[\d-]{4,})\s+(\d+)\s*$"
)


def _amount(value: str) -> float:
    try:
        return float(str(value or "").replace(",", "").strip())
    except (TypeError, ValueError):
        return 0.0


def _reverse_hebrew_tokens(value: str) -> str:
    """סדר חזותי → לוגי ברמת הריצה: הופך את סדר הריצות ואת אותיות הריצות
    העבריות; מספרים ולטינית לא נפגעים (33*181.5 חוזר להיות 181.5*33)."""
    runs = _RUN_RE.findall(value or "")
    restored = [run[::-1] if _HEBREW_CHAR.search(run) else run for run in reversed(runs)]
    return normalize_ws("".join(restored))


def detect(raw_text: str) -> bool:
    text = _ZERO_WIDTH.sub("", raw_text or "")
    return (
        CUSTOMER_TAX_ID in text
        or "kpym.co.il" in text.lower()
        or "לגס דהירפ" in text
        or "פריהד סגל" in text
    )


def _extract_items(lines: list[str]) -> list[POItem]:
    items: list[POItem] = []
    for line in lines:
        match = _ITEM_LINE.match(line)
        if not match:
            continue
        items.append(
            POItem(
                sku=match.group(5),
                description=_reverse_hebrew_tokens(match.group(4)) or "פריט לא זוהה",
                unit="יח'",
                quantity=_amount(match.group(3)),
                unit_price=_amount(match.group(2)),
                line_total=_amount(match.group(1)),
            )
        )
    return items


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

    m = re.search(r"([\d.,]+)\s+ללוכ ריחמ", full_text)
    if m:
        header["subtotal"] = _amount(m.group(1))

    m = re.search(r'([\d.,]+)\s+\(18\.00%\)\s+מ"עמ', full_text)
    if m:
        header["vat"] = _amount(m.group(1))

    m = re.search(r'ILS\s+([\d.,]+)\s+ריחמ כ"הס', full_text)
    if m:
        header["total"] = _amount(m.group(1))

    # בכוונה לא ממלאים את טלפון המשרד (03-681-0497): הטלפון שרלוונטי להזמנה
    # הוא של האיש באתר שמקבל את המשלוח, והוא נוסע על איש הקשר. אסור גם להעתיק
    # אותו ל-customer_phone — הסניטציה הגלובלית (to_purchase_order) מוחקת
    # איש קשר שהטלפון שלו זהה לטלפון הלקוח.

    emails = re.findall(r"[\w.-]+@[\w.-]+\.\w+", full_text)
    header["customer_email"] = next((e for e in emails if e.lower().startswith("finance@")), emails[0] if emails else "")

    # פרויקט: השורה שמסתיימת ב":טקיורפ" בדיוק — לא "טקיורפ להנמ" (מנהל פרויקט)
    m = re.search(r"^(.+?)\s*:\s*טקיורפ$", full_text, re.MULTILINE)
    if m:
        header["project"] = _reverse_hebrew_tokens(m.group(1))

    project_manager = ""
    m = re.search(r"^(.+?)\s*:\s*טקיורפ להנמ$", full_text, re.MULTILINE)
    if m:
        project_manager = _reverse_hebrew_tokens(m.group(1))

    # איש קשר בבלוק הכתובת: "טלפון: דוד- 050-9033833". שורת "אסף - 054-7720142"
    # היא אנחנו — מסוננת לפי הטלפון שלנו.
    for m in re.finditer(r"(0\d{1,2}-?\d{7})\s*-\s*([א-ת]+)\s*:\s*ןופלט", full_text):
        phone = m.group(1)
        if re.sub(r"\D", "", phone) == OUR_PHONE_DIGITS:
            continue
        name = _reverse_hebrew_tokens(m.group(2))
        # אם מנהל הפרויקט הוא אותו אדם (למשל "דוד" ⊂ "דוד בונדרצ'וק") — השם המלא עדיף
        if project_manager and name and name in project_manager:
            name = project_manager
        header["contact_name"] = name
        header["contact_phone"] = phone
        break
    if not header["contact_name"] and project_manager:
        header["contact_name"] = project_manager

    # כתובת האספקה — כמו ברם אדרת: החלק שלפני שם הספק שלנו בשורת "לכבוד",
    # אחרי הסרת חותמת ההדפסה; והשורה הבאה בלי הרחוב שלנו ("הגורן 34")
    address_parts: list[str] = []
    for index, line in enumerate(lines):
        if "ליטסקט תונורתפ בקעי ןב" not in line:
            continue
        site_visual = line.split("ליטסקט תונורתפ בקעי ןב", 1)[0]
        site_visual = re.sub(r"\d{2}/\d{2}/\d{2}\s+\d{2}:\d{2}\s*:\s*הספדה ךיראת", "", site_visual)
        site_name = _reverse_hebrew_tokens(site_visual)
        if site_name:
            address_parts.append(site_name)
        if index + 1 < len(lines):
            street_visual = lines[index + 1].replace("34 ןרוגה", "").strip()
            street = _reverse_hebrew_tokens(street_visual)
            if street:
                address_parts.append(street)
        break
    header["delivery_address"] = ", ".join(address_parts)

    items = _extract_items(lines)
    if not items:
        items = [POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0, sku="", unit="יח'")]

    items_total = round(sum(item.line_total or 0 for item in items), 2)
    if not header["subtotal"] and items_total:
        header["subtotal"] = items_total
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
