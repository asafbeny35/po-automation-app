import re
from pathlib import Path
import pdfplumber

try:
    import pytesseract
except Exception:  # pragma: no cover - optional in hosted runtimes
    pytesseract = None

try:
    from pdf2image import convert_from_path
except Exception:  # pragma: no cover - optional in hosted runtimes
    convert_from_path = None

from services.models import PurchaseOrderData, POItem

FORBIDDEN_CONTACT_PHONES = {
    "0547720142",
    "0505204010",
    "0503011503",
}

SUPPLIER_NAME_TOKENS = (
    "בן יעקב",
    "אסף",
    "דודי",
    "אבא",
    "אמא",
    "אבי",
)


def extract_text_pdfplumber(pdf_path: str | Path) -> str:
    pages = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


def ocr_pdf(pdf_path: str | Path) -> str:
    from services.ocr_service import ocr_pdf_via_vision
    return ocr_pdf_via_vision(Path(pdf_path))


def normalize_ws(value: str) -> str:
    return " ".join((value or "").split()).strip()


def first_match(pattern: str, text: str, flags=re.MULTILINE | re.IGNORECASE):
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else ""



def normalize_amount(value):
    if value is None:
        return None

    value = str(value)

    # ניקוי טקסט
    value = value.replace("₪", "").replace('ש"ח', "").replace("שח", "").strip()

    # תיקון RTL (מספרים הפוכים)
    if "," in value and "." in value:
        parts = value.split(",")
        if len(parts) == 2:
            left = parts[0].replace(".", "")
            right = parts[1]
            if left.isdigit() and right.isdigit():
                value = right + left

    # ניקוי פסיקים
    value = value.replace(",", "")

    try:
        return float(value)
    except Exception:
        return None


def normalize_date(value: str | None) -> str:
    value = normalize_ws(value or "")
    if not value:
        return ""
    m = re.search(r"(\d{2})/(\d{2})/(\d{4})", value)
    if m:
        return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    m = re.search(r"(\d{2})/(\d{2})/(\d{2})", value)
    if m:
        yy = int(m.group(3))
        return f"{m.group(1)}/{m.group(2)}/{2000 + yy}"
    return value


def normalize_po_number(raw: str | None) -> str:
    raw = normalize_ws(raw or "")
    if not raw:
        return ""
    raw = raw.replace(" ", "").lstrip("-")
    m = re.match(r"(\d+)PO$", raw, re.IGNORECASE)
    if m:
        return f"PO{m.group(1)}"
    m = re.match(r"PO(\d+)$", raw, re.IGNORECASE)
    if m:
        return f"PO{m.group(1)}"
    return raw


def build_footer(po_number="", project="", delivery_address="", contact_name="", contact_phone=""):
    parts = []
    if po_number:
        parts.append(f"הזמנת רכש {po_number}")
    if project:
        parts.append(f"פרויקט: {project}")
    if delivery_address:
        parts.append(f"כתובת לאספקה: {delivery_address}")
    if contact_name:
        parts.append(f"איש קשר: {contact_name}")
    if contact_phone:
        parts.append(f"טל': {contact_phone}")
    return " | ".join(parts)


def phone_digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def is_forbidden_contact_phone(value: str | None, customer_phone: str | None = None) -> bool:
    digits = phone_digits(value)
    if not digits:
        return False
    if digits in FORBIDDEN_CONTACT_PHONES:
        return True
    if customer_phone and digits == phone_digits(customer_phone):
        return True
    return False


def is_supplier_contact_name(value: str | None) -> bool:
    clean = normalize_ws(value or "")
    if not clean:
        return False
    if "טלפון" in clean or "נייד" in clean:
        return True
    return any(token in clean for token in SUPPLIER_NAME_TOKENS)


def sanitize_contact_pair(contact_name: str | None, contact_phone: str | None, customer_phone: str | None = None):
    clean_name = normalize_ws(contact_name or "")
    clean_phone = normalize_ws(contact_phone or "")

    if is_forbidden_contact_phone(clean_phone, customer_phone=customer_phone):
        clean_phone = ""
    if is_supplier_contact_name(clean_name):
        clean_name = ""

    if clean_name and not clean_phone:
        return clean_name, ""
    if clean_phone and not clean_name:
        return "", clean_phone
    return clean_name, clean_phone


def common_fields(text: str):
    customer_email = (
        first_match(r"e-?mail[:\s]*([^\s]+@[^\s]+)", text)
        or first_match(r"מייל[:,\s]*([^\s]+@[^\s]+)", text)
    )

    customer_id = (
        first_match(r"מספר תיק במע[\"״]מ[:\s]*([0-9]{6,12})", text)
        or first_match(r"עוסק מורשה[:\s]*([0-9]{6,12})", text)
        or first_match(r"ח\.?פ[:\s,()]*([0-9]{6,12})", text)
        or first_match(r"ח\.?פ\s*([0-9]{6,12})", text)
    )

    raw_po = (
        first_match(r"הזמנת רכש מספר\s*-?\s*([A-Za-z0-9\-/]+)", text)
        or first_match(r"ברקוד מספר תעודה[:\s]*\*?([A-Za-z0-9\-/]+)\*?", text)
        or first_match(r"הזמנת רכש מס[\":\s]*([A-Za-z0-9\-/]+)", text)
        or first_match(r"הזמנה מס[\"׳']\s*[:\-]?\s*([A-Za-z0-9\-/]+)", text)
        or first_match(r"הזמנת רכש\s*([A-Za-z0-9\-/]+)", text)
    )
    po_number = normalize_po_number(raw_po)

    po_date = (
        first_match(r"תאריך הזמנה[:\s]*([0-9./-]+)", text)
        or first_match(r"תאריך ההזמנה[:\s]*([0-9./-]+)", text)
        or first_match(r"תאריך[:\s]*([0-9./-]+)", text)
    )
    po_date = normalize_date(po_date)

    subtotal = (
        normalize_amount(first_match(r"סה[\"״]?כ חייב במע[\"״]מ[:\s]*([0-9,]+(?:\.\d{1,2})?)", text))
        or normalize_amount(first_match(r"מחיר כולל\s*([0-9,]+(?:\.\d{1,2})?)", text))
        or normalize_amount(first_match(r"סה[\"״]?כ הזמנה[:\s]*([0-9,]+(?:\.\d{1,2})?)", text))
        or normalize_amount(first_match(r"סה[\"״]?כ לפני מע[\"״]מ[:\s]*([0-9,]+(?:\.\d{1,2})?)", text))
    )

    vat = (
        normalize_amount(first_match(r"מע.?מ.*?([0-9,]+(?:\.\d{1,2})?)", text))
        or normalize_amount(first_match(r"מע[\"״]מ[:\s]*%?\s*[0-9.]+\s*([0-9,]+(?:\.\d{1,2})?)", text))
    )

    total = (
        normalize_amount(first_match(r"סה.?כ מסמך[:\s]*([0-9,]+(?:\.\d{1,2})?)", text))
        or normalize_amount(first_match(r"סה.?כ מחיר כולל מע[\"״]מ[:\s]*([0-9,]+(?:\.\d{1,2})?)", text))
        or normalize_amount(first_match(r"סה.?כ מחיר[:\s]*([0-9,]+(?:\.\d{1,2})?)", text))
        or normalize_amount(first_match(r"סה.?כ לתשלום[:\s]*([0-9,]+(?:\.\d{1,2})?)", text))
    )

    if subtotal is None and total is not None:
        subtotal = round(total / 1.18, 2)
    if total is None and subtotal is not None:
        total = round(subtotal * 1.18, 2)
    if vat is None and subtotal is not None and total is not None:
        vat = round(total - subtotal, 2)

    payment_terms_days = None
    payment_terms_label = ""
    payment_line = first_match(r"תנאי תשלום[:\s]*(.+)", text)
    if payment_line:
        payment_terms_label = normalize_ws(payment_line)
        m = re.search(r"(\d+)", payment_line)
        if m:
            payment_terms_days = int(m.group(1))

    project = normalize_ws(first_match(r"פרויקט[:\s]*([^\n]+)", text))

    delivery_address = normalize_ws(
        first_match(r"כתובת(?: למשלוח| לאספקה| פרויקט)?[:\s]*([^\n]+(?:\n[^\n]+){0,2})", text, flags=re.MULTILINE)
    )

    contact_name = (
        first_match(r"איש קשר[:\s]*([^\n]+)", text)
        or first_match(r"לידי[:\s]*([^\n]+)", text)
        or first_match(r"שם המזמין[:\s]*([^\n]+)", text)
    )

    contact_phone = (
        first_match(r"טל(?:פון)?(?: נייד)?[:'\" ]*([0-9.\-]+)", text)
        or first_match(r"(0\d{1,2}-\d{7})", text)
    )

    customer_phone = first_match(r"טלפון[:\s,]*([0-9.\-]+)", text)

    return {
        "customer_email": normalize_ws(customer_email),
        "customer_id": normalize_ws(customer_id),
        "po_number": po_number,
        "po_date": po_date,
        "subtotal": subtotal,
        "vat": vat,
        "total": total,
        "payment_terms_days": payment_terms_days,
        "payment_terms_label": payment_terms_label,
        "project": project,
        "delivery_address": delivery_address,
        "contact_name": normalize_ws(contact_name),
        "contact_phone": normalize_ws(contact_phone),
        "customer_phone": normalize_ws(customer_phone),
    }


def to_purchase_order(customer_name: str, items: list[POItem], header: dict, raw_text: str) -> PurchaseOrderData:
    contact_name, contact_phone = sanitize_contact_pair(
        header.get("contact_name", ""),
        header.get("contact_phone", ""),
        customer_phone=header.get("customer_phone", ""),
    )
    header["contact_name"] = contact_name
    header["contact_phone"] = contact_phone

    first_item = items[0] if items else POItem(description="", quantity=1, unit_price=0, line_total=0)
    safe_items = []
    for item in items or []:
        safe_items.append(
            POItem(
                description=item.description or "",
                quantity=item.quantity or 0,
                unit_price=item.unit_price or 0,
                line_total=item.line_total or 0,
                sku=item.sku or "",
                unit=getattr(item, "unit", "") or "",
            )
        )

    footer_text = build_footer(
        po_number=header.get("po_number", ""),
        project=header.get("project", ""),
        delivery_address=header.get("delivery_address", ""),
        contact_name=header.get("contact_name", ""),
        contact_phone=header.get("contact_phone", ""),
    )

    return PurchaseOrderData(
        po_number=header.get("po_number", ""),
        po_date=normalize_date(header.get("po_date", "")),
        customer_name=customer_name or header.get("customer_name", ""),
        customer_id=header.get("customer_id", ""),
        customer_email=header.get("customer_email", ""),
        customer_phone=header.get("customer_phone", ""),
        delivery_address=header.get("delivery_address", ""),
        project=header.get("project", ""),
        contact_name=header.get("contact_name", ""),
        contact_phone=header.get("contact_phone", ""),
        subtotal=header.get("subtotal") or 0,
        vat=header.get("vat") or 0,
        total=header.get("total") or 0,
        payment_terms_days=header.get("payment_terms_days"),
        payment_terms_label=header.get("payment_terms_label", ""),
        items=safe_items,
        raw_text=raw_text,
        extra={
            "project": header.get("project", ""),
            "contact_name": header.get("contact_name", ""),
            "contact_phone": header.get("contact_phone", ""),
            "footer_text": footer_text,
            "item_description": first_item.description,
            "item_sku": first_item.sku or "",
            "item_unit": getattr(first_item, "unit", "") or "",
            "item_quantity": first_item.quantity,
            "item_unit_price": first_item.unit_price,
            "item_line_total": first_item.line_total,
        },
    )


def fix_hebrew_text(text: str) -> str:
    lines = text.split("\n")
    fixed = []

    for line in lines:
        # אם יש הרבה עברית → נהפוך
        if sum(1 for c in line if 'א' <= c <= 'ת') > 3:
            fixed.append(line[::-1])
        else:
            fixed.append(line)

    return "\n".join(fixed)


def _is_mostly_hebrew(token: str) -> bool:
    return sum(1 for c in token if "א" <= c <= "ת") > len(token) / 2


def fix_hebrew_rtl_text(text: str) -> str:
    """
    Better RTL fixer for Hebrew PDFs where pdfplumber returns visual order.

    fix_hebrew_text() does line[::-1] which also reverses numbers/dates/amounts.
    This function reverses TOKEN ORDER and only character-reverses Hebrew tokens,
    leaving numbers, dates, prices and SKUs intact.

    Use this for SAP / Israeli ERP PDFs (e.g. shponder_pedlon) where numbers are
    already in correct LTR order inside a RTL visual line.
    """
    lines = text.split("\n")
    fixed = []
    for line in lines:
        if sum(1 for c in line if "א" <= c <= "ת") > 3:
            tokens = line.split()
            fixed_tokens = [
                token[::-1] if _is_mostly_hebrew(token) else token
                for token in reversed(tokens)
            ]
            fixed.append(" ".join(fixed_tokens))
        else:
            fixed.append(line)
    return "\n".join(fixed)
