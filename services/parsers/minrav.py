"""פרסר "הזמנת רכש" של מנרב בנייה (קבוצת מנרב).

המסמך טומן ארבע מלכודות, וכל אחת מהן הייתה מייצרת הזמנה שגויה בשקט:

1. **ארבעה מספרים בני 9 ספרות** מתנוססים על העמוד: עוסק מורשה 520034505,
   תיק במע"מ 557480977, תיק ניכויים 951025360, ובתוך מסגרת "לכבוד" גם
   037017779 — שהוא *שלנו*. המסמך מורה מפורשות "וחובה לציין ח.פ 520034505",
   ולכן זו השורה שקובעת, ולא ההתאמה הראשונה של תשע ספרות.

2. **הכותרת היא שלוש עמודות** שנדחסות לשורת טקסט אחת: "לכבוד" (הכתובת שלנו),
   "כתובת למשלוח" (היעד), ופרטי הקניין. פיצול נאיבי לפי שורות היה נותן
   ככתובת אספקה את "בן יעקב פתרונות טקסטיל מגדלי עמים טאוורס קניין: אביב סבג".
   לכן היעד נחתך לפי מיקום המילים על העמוד.

3. **שני אנשי קשר ושני טלפונים** באותה שורה: "לידי: אסף / 0547720142" זה אנחנו,
   ו-"הזמנות לידי: רון דרור / 054-5081549" זה הלקוח.

4. **שלוש שורות פריט זהות** — אותו מק"ט ואותו תיאור, ונבדלות רק במידה שמופיעה
   בשורת ההמשך (230/96, 220/96, 210/94). בלי המידה מתקבלות שלוש שורות זהות.
"""

from __future__ import annotations

import re

from services.models import POItem
from services.parsers.common import fix_hebrew_rtl_text

# השם כפי שהלקוח רשום בקטלוג, כדי להתחבר לכרטיס הקיים ולא לפתוח כפול. השם
# המשפטי המלא שהמסמך דורש לחשבונית — 'קבוצת מנרב בע"מ – מנרב הנדסה ובנייה' —
# נשמר ב-extra תחת legal_billing_name, יחד עם ח.פ 520034505 שחובה לציין.
CUSTOMER_NAME = "קבוצת מנרב"
LEGAL_BILLING_NAME = 'קבוצת מנרב בע"מ - מנרב הנדסה ובנייה'
INVOICE_EMAIL = "invoice@minrav.co.il"

# מספרי הזיהוי של בן יעקב, שמופיעים במסגרת "לכבוד" ואסור שייקלטו כלקוח.
_OUR_IDS = {"037017779", "3032434"}
_OUR_PHONES = {"0547720142", "054-7720142"}

_MARKERS = ("מנרב", "minrav.co.il")


def _amount(value: str) -> float:
    cleaned = re.sub(r"[^\d.\-]", "", str(value or "").replace(",", ""))
    return float(cleaned) if cleaned not in ("", "-", ".") else 0.0


def _normalize_date(value: str) -> str:
    parts = str(value or "").strip().split("/")
    if len(parts) != 3:
        return str(value or "").strip()
    day, month, year = parts
    if len(year) == 2:
        year = f"20{year}"
    return f"{day.zfill(2)}/{month.zfill(2)}/{year}"


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if len(digits) == 10 and digits.startswith("05"):
        return f"{digits[:3]}-{digits[3:]}"
    if len(digits) == 9 and digits.startswith("0"):
        return f"{digits[:2]}-{digits[2:]}"
    return str(value or "").strip()


def _mostly_hebrew(token: str) -> bool:
    return sum(1 for c in token if "א" <= c <= "ת") > len(token) / 2


def _delivery_from_layout(pdf_path) -> str:
    """כתובת האספקה נחתכת לפי מיקום המילים, כי בטקסט היא מעורבבת עם שתי עמודות.

    העוגנים הם תוויות שלוש העמודות — "לכבוד", "כתובת למשלוח" ו"תאריך הזמנה" —
    והגבולות הם אמצע המרחק ביניהן. כך אין תלות במספרים קבועים של הפריסה.
    """
    try:
        import pdfplumber

        with pdfplumber.open(pdf_path) as pdf:
            words = pdf.pages[0].extract_words()
    except Exception:
        return ""

    def anchor(visual: str) -> float | None:
        hits = [w["x0"] for w in words if w["text"] == visual]
        return max(hits) if hits else None

    to_label, ship_label, date_label = anchor(":דובכל"), anchor("תבותכ"), anchor("ךיראת")
    if to_label is None or ship_label is None or date_label is None:
        return ""
    right_edge = (to_label + ship_label) / 2      # בין "לכבוד" ל"כתובת למשלוח"
    left_edge = (ship_label + date_label) / 2     # בין "כתובת למשלוח" ל"תאריך הזמנה"

    ship_top = min((w["top"] for w in words if w["text"] == "תבותכ"), default=None)
    stop_top = min((w["top"] for w in words if w["text"] == ":ידיל" and w["x0"] > right_edge), default=None)
    if ship_top is None:
        return ""

    rows: dict[int, list] = {}
    for word in words:
        if not (left_edge < word["x0"] <= right_edge):
            continue
        if word["top"] <= ship_top + 2:                       # שורת התווית עצמה
            continue
        if stop_top is not None and word["top"] >= stop_top - 2:   # מ-"לידי" והלאה
            continue
        rows.setdefault(round(word["top"] / 6) * 6, []).append(word)

    lines = []
    for top in sorted(rows):
        ordered = sorted(rows[top], key=lambda w: -w["x0"])
        line = " ".join(t["text"][::-1] if _mostly_hebrew(t["text"]) else t["text"] for t in ordered)
        line = line.strip()
        if line:
            lines.append(line)
    return ", ".join(lines)


def _delivery_from_text(logical: str) -> str:
    """גיבוי כשאין קובץ: חותכים מהשורה המשולבת את העמודה שלנו ואת עמודת הקניין."""
    lines = logical.splitlines()
    start = next((i for i, l in enumerate(lines) if "כתובת למשלוח" in l), -1)
    stop = next((i for i, l in enumerate(lines) if re.search(r"(?<!הזמנות )לידי:", l)), len(lines))
    if start < 0:
        return ""
    parts = []
    for line in lines[start + 1:stop]:
        chunk = re.split(r"קניין:|דואר אלקטרוני:|תאריך הדפסה:", line)[0]
        chunk = re.sub(r"בן יעקב פתרונות טקסטיל|הגורן\s*\d+|\S*\s*3032434", "", chunk)
        chunk = re.sub(r"\s+", " ", chunk).strip(" ,")
        if chunk:
            parts.append(chunk)
    return ", ".join(parts)


def _items(logical: str) -> list[POItem]:
    """שורה | מק"ט | תאור מוצר | ת.אספקה | מס' פרויקט | כמות | יתרה | מחיר ליח' | סה"כ"""
    pattern = re.compile(
        r"^\s*\d+\s+(\d{6,})\s+(.+?)\s+\d{2}/\d{2}/\d{2,4}\s+(\S+)\s+"
        r"([\d,]+\.\d+)\s+(\S+)\s+[\d,]+\.\d+\s+\S+\s+([\d,]+\.\d+)\s+\S+\s+([\d,]+\.\d{2})\s*$"
    )
    lines = logical.splitlines()
    items: list[POItem] = []
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        description = match.group(2).strip()
        # שורת ההמשך נושאת את המידה, וזה מה שמבדיל בין שורות עם אותו מק"ט
        if index + 1 < len(lines):
            tail = lines[index + 1].strip()
            if re.fullmatch(r"\d+\s*/\s*\d+", tail):
                description = f"{description} {tail}"
        items.append(POItem(
            sku=match.group(1),
            description=re.sub(r"\s+", " ", description),
            quantity=_amount(match.group(4)),
            unit_price=_amount(match.group(6)),
            line_total=_amount(match.group(7)),
            unit=match.group(5).strip().replace("יחי", "יח'"),
        ))
    return items


def parse(text: str, pdf_path=None):
    raw_text = str(text or "")
    logical = fix_hebrew_rtl_text(raw_text)
    if not any(marker in logical for marker in _MARKERS) or "הזמנת רכש" not in logical:
        return None

    def find(pattern: str, group: int = 1) -> str:
        match = re.search(pattern, logical, re.MULTILINE)
        return match.group(group).strip() if match else ""

    items = _items(logical)
    if not items:
        return None

    # ח.פ לחיוב — לפי ההוראה המפורשת במסמך, ולא לפי המספר הראשון בעמוד.
    customer_id = find(r"וחובה לציין ח\.פ\s*(\d{8,9})") or find(r"^עוסק מורשה:\s*(\d{8,9})")
    if customer_id in _OUR_IDS:
        customer_id = ""

    header = {
        "customer_id": customer_id,
        "po_number": find(r"הזמנת רכש מספר\s+(\S+)"),
        "po_date": _normalize_date(find(r"תאריך הזמנה:\s*(\d{2}/\d{2}/\d{2,4})")),
        "subtotal": _amount(find(r"^מחיר כולל\s+([\d,]+\.\d{2})")),
        "vat": _amount(find(r'מע"מ\s*\([\d.]+%\)\s*([\d,]+\.\d{2})')),
        "total": _amount(find(r'^סה"כ מחיר\s+([\d,]+\.\d{2})')),
        "payment_terms_days": None,
        "payment_terms_label": "",
        "project": find(r"^פרויקט:\s*(.+?)\s*$"),
        "delivery_address": _delivery_from_layout(pdf_path) if pdf_path else "",
        "contact_name": find(r"הזמנות לידי:\s*(.+?)\s*$"),
        "contact_phone": "",
        "customer_email": find(r"ולשלוח למייל\s+(\S+@\S+)") or INVOICE_EMAIL,
        "customer_phone": _normalize_phone(find(r"^טלפון:\s*,?\s*(0\d{1,2}-?\d{7})")),
    }
    if not header["delivery_address"]:
        header["delivery_address"] = _delivery_from_text(logical)

    days = find(r"תנאי תשלום:\s*(\d+)")
    if days:
        header["payment_terms_days"] = int(days)
        header["payment_terms_label"] = f"שוטף + {days}"

    # הטלפון של איש הקשר יושב בשורה שאחרי "הזמנות לידי", לצד הטלפון שלנו.
    lines = logical.splitlines()
    contact_row = next((i for i, l in enumerate(lines) if "הזמנות לידי:" in l), -1)
    if contact_row >= 0 and contact_row + 1 < len(lines):
        phones = [p for p in re.findall(r"0\d{1,2}-?\d{7}", lines[contact_row + 1]) if p not in _OUR_PHONES]
        if phones:
            header["contact_phone"] = _normalize_phone(phones[-1])

    header["extra"] = {
        "supplier_number": find(r"מס' ספק:\s*(\d+)"),
        "requisition_number": find(r"מספר דרישה:\s*(\S+)"),
        "buyer_name": find(r"קניין:\s*(.+?)\s*$"),
        "buyer_email": find(r"דואר אלקטרוני:\s*(\S+@\S+)"),
        "legal_billing_name": LEGAL_BILLING_NAME,
    }
    return CUSTOMER_NAME, items, header
