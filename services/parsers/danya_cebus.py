"""
Parser for דניה סיבוס בע"מ purchase orders.

These PDFs store text in RTL visual order. pdfplumber extracts characters
left-to-right across the page, which means:
  - Hebrew characters appear reversed (right-to-left word order is inverted)
  - Numbers/ASCII appear CORRECT (they are LTR even in RTL text)
  - Dates appear CORRECT for the same reason

Strategy: work with raw extracted text.  Numbers/dates are ready to use.
For Hebrew strings (names, descriptions) we extract the reversed token and
call _unheb() which reverses character order to recover readable Hebrew.
"""

import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws

CUSTOMER_NAME = 'דניה סיבוס בע"מ'
CUSTOMER_ID = "512569237"

# As pdfplumber sees the text (Hebrew reversed, kept for detection)
_REVERSED_MARKER = 'מ"עב סוביס הינד'
_EMAIL_DOMAIN = "danya-cebus.co.il"


# ── helpers ──────────────────────────────────────────────────────────────────

def _clean(s: str) -> str:
    return normalize_ws(re.sub(r"[‎‏‪-‮]", "", s or ""))


def _unheb(s: str) -> str:
    """Reverse character order of a Hebrew-only string to restore readability."""
    return _clean(s)[::-1]


def _amount(s: str) -> float:
    cleaned = re.sub(r"[^\d.]", "", (s or "").replace(",", ""))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def _lines(text: str) -> list[str]:
    return [_clean(line) for line in (text or "").splitlines() if _clean(line)]


def _first(pattern: str, text: str, flags: int = 0) -> str:
    m = re.search(pattern, text, flags)
    return _clean(m.group(1)) if m else ""


def _detect(text: str) -> bool:
    t = _clean(text)
    return _REVERSED_MARKER in t or _EMAIL_DOMAIN in t.lower()


def _extract_email(text: str) -> str:
    # Email is LTR so it appears correctly, but may be surrounded by reversed label
    m = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text, re.IGNORECASE)
    return m.group(0) if m else ""


# ── item extraction ───────────────────────────────────────────────────────────
#
# Raw extracted item line (Hebrew reversed, numbers correct):
#   4,900.00 {supplier_snippet_reversed} חש 98.00 חי 50.00 {desc_reversed}{SKU} 1
#
# Fields in order (left→right in extracted string = right→left on page):
#   line_total | supplier_snippet | "חש" | unit_price | "חי" | qty | desc+SKU | row_num

_ITEM_RE = re.compile(
    r"^([\d,]+\.\d{2})"       # line total
    r"\s+.+?"                  # supplier snippet (skip)
    r"\s+חש\s+"                # "ש\"ח" reversed
    r"([\d,]+\.\d{2})"        # unit price
    r"\s+חי\s+"                # "יח" reversed
    r"([\d,]+\.\d{2})"        # quantity
    r"\s+"
    r"([א-ת][\s\S]*?)"        # description (reversed Hebrew)
    r"(\d{5,})"                # SKU
    r"\s+(\d+)$",              # row number
    re.UNICODE,
)


def _parse_items(raw_lines: list[str]) -> list[POItem]:
    items: list[POItem] = []
    for line in raw_lines:
        m = _ITEM_RE.match(line.strip())
        if m:
            desc_reversed = _clean(m.group(4))
            desc = _unheb(desc_reversed)
            items.append(POItem(
                sku=m.group(5),
                description=desc or "פריט לא זוהה",
                quantity=_amount(m.group(3)),
                unit_price=_amount(m.group(2)),
                line_total=_amount(m.group(1)),
                unit="יח'",
            ))
    return items or [POItem(description="פריט לא זוהה", quantity=1, unit_price=0.0, line_total=0.0, sku="", unit="")]


# ── main parse ────────────────────────────────────────────────────────────────

def parse(text: str):
    if not _detect(text):
        return None

    raw_lines = _lines(text)
    flat = "\n".join(raw_lines)

    # PO number: "D260044580 'סמ םירמוח תנמזה" → number is LTR, correct
    po_number = _first(r"([A-Z]\d{6,})\s+'סמ\s+", flat)
    if not po_number:
        po_number = _first(r"\b(D\d{6,})\b", flat)

    # Date: "24/06/26 :הנמזה ךיראת" — date is LTR, correct
    po_date_raw = _first(r"(\d{2}/\d{2}/\d{2,4})\s*:הנמזה ךיראת", flat)
    if not po_date_raw:
        po_date_raw = _first(r"(\d{2}/\d{2}/\d{2,4})", flat)
    po_date = normalize_date(po_date_raw)

    # Payment: "75 + ףטוש :םולשת יאנת" → number 75 is LTR, correct
    payment_days: int | None = None
    pm = re.search(r"(\d+)\s*\+\s*ףטוש", flat)
    if pm:
        payment_days = int(pm.group(1))
    payment_label = f"שוטף + {payment_days}" if payment_days is not None else ""

    # Totals
    # Grand total: "חש 5,782.00 ריחמ כ"הס" — number correct
    total = _amount(_first(r'חש\s+([\d,]+\.\d{2})\s+ריחמ\s+כ"הס', flat))

    # VAT: "882.00 (18.00%) מ"עמ"
    vat = 0.0
    vat_rate = 0.0
    vm = re.search(r'([\d,]+\.\d{2})\s+\(([\d.]+)%\)\s+מ"עמ', flat)
    if vm:
        vat = _amount(vm.group(1))
        vat_rate = _amount(vm.group(2))

    # Subtotal from "כולל מחיר": "4,900.00 ללוכ ריחמ"
    subtotal = _amount(_first(r"([\d,]+\.\d{2})\s+ללוכ ריחמ", flat))
    if not subtotal and total and vat:
        subtotal = round(total - vat, 2)

    # Office orderer (ניצן גולן) — kept in extra, not the field contact
    orderer_reversed = _first(r"(.+?)\s*:ןימזמה םש", flat)
    orderer_name = _unheb(orderer_reversed) if orderer_reversed else ""
    contact_name = ""

    # Field contact: ויקטור — phone is glued to the reversed name "רוטקיו"
    # Raw pattern: "050-2898973רוטקיו"
    victor_match = re.search(r"(0\d{2}-\d{6,7})רוטקיו", flat)
    if victor_match:
        contact_name = "ויקטור"
        logistics_phone = victor_match.group(1)
    else:
        # fallback: first mobile in document
        phones = re.findall(r"0\d{1,2}-\d{6,7}", flat)
        logistics_phone = phones[0] if phones else ""

    # Logistics helper: "054-544-7208 :ןופלטב ןינקעו ףסוי :יטסיגול רזוע"
    logistics_note = ""
    lm = re.search(r"(0\d{2}-\d{3}-\d{4})\s*:ןופלטב\s+(.+?)\s*:יטסיגול רזוע", flat)
    if lm:
        helper_phone = lm.group(1)
        helper_name = _unheb(lm.group(2))
        logistics_note = f"עוזר לוגיסטי: {helper_name} | {helper_phone}"

    # Email
    customer_email = _extract_email(flat)

    # Supplier number
    supplier_no = _first(r"([\d]+)\s*:קפס\s+'סמ", flat)

    items = _parse_items(raw_lines)

    header = {
        "customer_name": CUSTOMER_NAME,
        "customer_id": CUSTOMER_ID,
        "customer_phone": "03-5383838",
        "customer_email": customer_email,
        "delivery_address": "",
        "po_number": po_number,
        "po_date": po_date,
        "subtotal": subtotal,
        "vat": vat,
        "total": total,
        "payment_terms_days": payment_days,
        "payment_terms_label": payment_label,
        "project": "",
        "contact_name": contact_name,
        "contact_phone": logistics_phone,
        "extra": {
            "vat_rate": vat_rate,
            "supplier_number": supplier_no,
            "orderer_name": orderer_name,
            "order_notes": logistics_note,
            "parser_name": "danya_cebus",
        },
    }

    return CUSTOMER_NAME, items, header
