"""
Parser for תדהר בניה בע"מ purchase orders.

Like Danya Cebus, Tidhar's PDFs store text in RTL visual order: pdfplumber reads
characters left-to-right across the page, so Hebrew words come out reversed while
numbers, dates, SKUs and emails come out correct.

The header is three columns on the same lines, which is why the address is taken
by x-coordinate rather than by regex — the "לכבוד" column (our own details) and
the "כתובת למשלוח" column share every line, and a text-only match picks the wrong
one. Column bands measured on the real form:

    x > 430          "לכבוד"          — our company, our contact, our phones
    240 <= x <= 325  "כתובת למשלוח"   — the site, its address and the site contact
    x < 190          dates, order email
"""

import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws

CUSTOMER_NAME = 'תדהר בניה בע"מ'
CUSTOMER_ID = "512043266"          # עוסק מורשה של תדהר (לא מספר תיק במע"מ 558427548)
CUSTOMER_PHONE = "09-7766111"

# As pdfplumber sees it (Hebrew reversed) — 'תדהר בניה בע"מ'
_REVERSED_MARKER = 'מ"עב הינב רהדת'
_EMAIL_DOMAIN = "tidhar.co.il"

# Our own details, so they are never mistaken for the customer's.
_OUR_DEALER_ID = "037017779"
_OUR_PHONES = {"0547720142", "054-7720142"}

# Delivery column band, measured on the form.
_ADDRESS_X_MIN, _ADDRESS_X_MAX = 235.0, 326.0


# ── helpers ──────────────────────────────────────────────────────────────────

def _clean(s: str) -> str:
    return normalize_ws(re.sub(r"[‎‏‪-‮]", "", s or ""))


def _unheb(s: str) -> str:
    """Restore a reversed RTL fragment: reverse token order, char-reverse Hebrew tokens."""
    tokens = _clean(s).split()
    return " ".join(t[::-1] if re.search(r"[א-ת]", t) else t for t in reversed(tokens))


def _amount(s: str) -> float:
    cleaned = re.sub(r"[^\d.]", "", (s or "").replace(",", ""))
    try:
        return float(cleaned) if cleaned else 0.0
    except ValueError:
        return 0.0


def _lines(text: str) -> list[str]:
    return [_clean(line) for line in (text or "").splitlines() if _clean(line)]


def _first(pattern: str, text: str, flags: int = 0) -> str:
    match = re.search(pattern, text, flags)
    return _clean(match.group(1)) if match else ""


def _detect(text: str) -> bool:
    cleaned = _clean(text)
    return (
        _REVERSED_MARKER in cleaned
        or _EMAIL_DOMAIN in cleaned.lower()
        or CUSTOMER_ID in cleaned
    )


# ── delivery block (coordinate based) ─────────────────────────────────────────

def _extract_delivery_block(pdf_path) -> dict:
    """Read the middle 'כתובת למשלוח' column: address lines, site contact and phone.

    Bounded to the header block — the same x band keeps running down the page into
    the item table and the supplier notes, and without a floor the address swallows
    the whole footer.
    """
    result = {"address": "", "contact_name": "", "contact_phone": ""}
    if not pdf_path:
        return result
    try:
        import pdfplumber
        from collections import defaultdict

        with pdfplumber.open(pdf_path) as pdf:
            words = pdf.pages[0].extract_words(x_tolerance=2, y_tolerance=3)

        # The header ends where the order number / item table begins.
        table_top = min(
            [w["top"] for w in words if re.fullmatch(r"POB\d{5,}", w["text"])]
            or [w["top"] for w in words if w["text"] == "הרוש"]
            or [260.0]
        )

        lines_by_y: dict[int, list] = defaultdict(list)
        for word in words:
            if _ADDRESS_X_MIN <= word["x0"] <= _ADDRESS_X_MAX and word["top"] < table_top:
                lines_by_y[round(word["top"] / 4) * 4].append(word)

        address_lines: list[str] = []
        for y in sorted(lines_by_y):
            row = sorted(lines_by_y[y], key=lambda w: -w["x0"])  # already RTL reading order
            # tokens are already ordered; only the characters inside each need flipping
            text = _clean(" ".join(
                t[::-1] if re.search(r"[א-ת]", t) else t
                for t in (w["text"] for w in row)
            ))
            if not text or "כתובת" in text or "למשלוח" in text:
                continue
            # from "לידי" downwards it is the site contact, not the address
            if text.startswith("לידי"):
                result["contact_name"] = _clean(text.split(":", 1)[-1])
                continue
            phone = re.search(r"0\d{1,2}-?\d{6,7}", text)
            if phone and ("טלפון" in text or "נייד" in text):
                candidate = phone.group(0)
                if candidate.replace("-", "") not in {p.replace("-", "") for p in _OUR_PHONES}:
                    result["contact_phone"] = result["contact_phone"] or candidate
                continue
            address_lines.append(text)

        result["address"] = ", ".join(dict.fromkeys(address_lines))
    except Exception:
        pass
    return result


# ── item extraction ───────────────────────────────────────────────────────────
#
# A row as pdfplumber extracts it (RTL, so read right-to-left on the page):
#
#   {required_for} {line_total} ILS {unit_price} {unit} {quantity} {supply_date}
#   {description…} {supplier_sku} {internal_sku} {row_number}
#
# Columns on the page: שורה | מק"ט | מק"ט ספק | תאור מוצר | ת. אספקה | כמות |
#                      מחיר ליחידה | סה"כ מחיר | נדרש עבור

_ITEM_RE = re.compile(
    r"^(?P<required_for>.*?)\s*"
    r"(?P<line_total>[\d,]+\.\d{2})\s+"
    r"(?:ILS|USD|EUR)\s+"
    r"(?P<unit_price>[\d,]+\.\d+)\s+"
    r"(?P<unit>\S+)\s+"
    r"(?P<quantity>[\d,]+\.\d+)\s+"
    r"(?P<supply_date>\d{2}/\d{2}/\d{2,4})\s+"
    r"(?P<description>.+?)\s+"
    r"(?P<supplier_sku>\S+)\s+"
    r"(?P<internal_sku>\S+)\s+"
    r"(?P<row_number>\d{1,3})$"
)


def _parse_items(raw_lines: list[str]) -> list[POItem]:
    items: list[POItem] = []
    for line in raw_lines:
        match = _ITEM_RE.match(line.strip())
        if not match:
            continue
        description = _unheb(match.group("description"))
        # Tidhar's own catalogue number is the internal one; the supplier SKU is ours.
        supplier_sku = _clean(match.group("supplier_sku"))
        items.append(POItem(
            sku=supplier_sku,
            description=description or "פריט לא זוהה",
            quantity=_amount(match.group("quantity")),
            unit_price=_amount(match.group("unit_price")),
            line_total=_amount(match.group("line_total")),
            unit=_unheb(match.group("unit")) or "יח'",
        ))
    return items


# ── main parse ────────────────────────────────────────────────────────────────

def parse(text: str, pdf_path=None):
    if not _detect(text):
        return None

    raw_lines = _lines(text)
    flat = "\n".join(raw_lines)

    # "POB2636264 רפסמ שכר תנמזה" — the number is LTR so it survives intact
    po_number = _first(r"([A-Z]{2,4}\d{5,})\s+רפסמ\s+שכר\s+תנמזה", flat)
    if not po_number:
        po_number = _first(r"\b(POB\d{5,})\b", flat)

    po_date = normalize_date(_first(r"(\d{2}/\d{2}/\d{2,4})\s*:הנמזה\s+ךיראת", flat))

    # "62ש" reads right-to-left as "ש62" — Tidhar's shorthand for שוטף + 62
    payment_days: int | None = None
    terms_match = re.search(r"(\d{1,3})ש\s*:םולשת\s+יאנת", flat)
    if not terms_match:
        terms_match = re.search(r":םולשת\s+יאנת\s+(\d{1,3})ש", flat)
    if terms_match:
        payment_days = int(terms_match.group(1))
    payment_label = f"שוטף + {payment_days}" if payment_days is not None else ""

    # Totals. "3,300.00 ללוכ ריחמ" / "594.00 (18.00%) מ\"עמ" / "ILS 3,894.00 ריחמ כ\"הס"
    subtotal = _amount(_first(r"([\d,]+\.\d{2})\s+ללוכ\s+ריחמ", flat))
    vat = 0.0
    vat_rate = 0.0
    vat_match = re.search(r'([\d,]+\.\d{2})\s+\(([\d.]+)%\)\s+מ"עמ', flat)
    if vat_match:
        vat = _amount(vat_match.group(1))
        vat_rate = _amount(vat_match.group(2))
    total = _amount(_first(r'(?:ILS|USD|EUR)\s+([\d,]+\.\d{2})\s+ריחמ\s+כ"הס', flat))
    if not total and subtotal:
        total = round(subtotal + vat, 2)

    # Project: number and description are separate fields on the form.
    project_number = _first(r"([A-Z]{2}\d{4,})\s*:טקיורפ\s+'סמ", flat)
    project_name = _unheb(_first(r"(.+?)\s*:טקיורפ\s+רואת", flat))
    project = " · ".join(part for part in (project_name, project_number) if part)

    buyer = _unheb(_first(r"(.+?)\s*:ןיינק", flat))

    # The order email belongs to the site contact, not to Tidhar head office.
    customer_email = ""
    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", flat)
    if email_match:
        customer_email = email_match.group(0)

    delivery = _extract_delivery_block(pdf_path)
    contact_name = delivery.get("contact_name") or ""
    contact_phone = delivery.get("contact_phone") or ""

    # Fallback when the PDF could not be re-opened: read the site contact from text,
    # skipping our own "לידי: אסף בן יעקב" line.
    if not contact_name:
        for candidate in re.findall(r"(.+?)\s*:ידיל", flat):
            name = _unheb(candidate)
            if name and "בן יעקב" not in name and "אסף" not in name:
                contact_name = name.split(",")[0].strip()
                break
    if not contact_phone:
        # רק מספר שצמוד לתווית "טלפון"/"נייד" — בלי זה מספר העוסק המורשה שלנו
        # (037017779) תואם לתבנית טלפון ונתפס בטעות.
        ours = {p.replace("-", "") for p in _OUR_PHONES} | {_OUR_DEALER_ID}
        for phone in re.findall(r"(0\d{1,2}-?\d{6,7})\s*:(?:דיינ\s+)?ןופלט", flat):
            normalized = phone.replace("-", "")
            if normalized in ours or normalized.startswith("097766"):
                continue  # שלנו, או המוקד הראשי של תדהר
            contact_phone = phone
            break

    items = _parse_items(raw_lines)
    if not items:
        items = [POItem(description="פריט לא זוהה", quantity=1, unit_price=0.0,
                        line_total=0.0, sku="", unit="")]

    header = {
        "customer_name": CUSTOMER_NAME,
        "customer_id": CUSTOMER_ID,
        "customer_phone": CUSTOMER_PHONE,
        "customer_email": customer_email,
        "delivery_address": delivery.get("address") or "",
        "po_number": po_number,
        "po_date": po_date,
        "subtotal": subtotal,
        "vat": vat,
        "total": total,
        "payment_terms_days": payment_days,
        "payment_terms_label": payment_label,
        "project": project,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "extra": {
            "vat_rate": vat_rate,
            "project_number": project_number,
            "project_name": project_name,
            "buyer_name": buyer,
            "parser_name": "tidhar",
        },
    }

    return CUSTOMER_NAME, items, header
