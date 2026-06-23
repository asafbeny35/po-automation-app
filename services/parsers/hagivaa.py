import re
from services.models import POItem
from services.parsers.common import common_fields, normalize_amount, normalize_ws, normalize_po_number, normalize_date


def parse(text: str):
    header = common_fields(text)
    customer_name = 'הגבעה י.ח. בע"מ'

    # מספר הזמנה
    m_po = re.search(r"הזמנת רכש מספר\s*-?([A-Za-z0-9]+)", text)
    if m_po:
        header["po_number"] = normalize_po_number(m_po.group(1))

    # תאריך
    m_date = re.search(r"תאריך ההזמנה:\s*([0-9/]+)", text)
    if m_date:
        header["po_date"] = normalize_date(m_date.group(1))

    # ח.פ
    m_id = re.search(r"ח\.פ\s*([0-9]{6,12})", text)
    if m_id:
        header["customer_id"] = m_id.group(1)

    # כתובת אספקה (2 שורות)
    m_addr = re.search(
        r"אספקה ל([^\n]+)\n([^\n]+)",
        text,
        re.MULTILINE
    )
    if m_addr:
        header["delivery_address"] = normalize_ws(
            m_addr.group(1) + " / " + m_addr.group(2)
        )

    # איש קשר (בלוק)
    m_contact = re.search(
        r"איש קשר:\s*\n\s*([^\d\n]+)\s+(0\d{1,2}-\d{7})",
        text,
        re.MULTILINE
    )
    if m_contact:
        header["contact_name"] = normalize_ws(m_contact.group(1))
        header["contact_phone"] = m_contact.group(2)

    # פריט (בלוק מפוצל שורות)
    m_item = re.search(
        r"כל אחד\s+([\d.,]+)\s+([\d.,]+)\s+(.+?)\nמ[\"״]?ר",
        text,
        re.MULTILINE | re.DOTALL
    )

    if m_item:
        unit_price = normalize_amount(m_item.group(1)) or 0
        qty = normalize_amount(m_item.group(2)) or 1
        desc = normalize_ws(m_item.group(3)) + ' מ"ר'

        item = POItem(
            description=desc,
            quantity=qty,
            unit_price=unit_price,
            line_total=round(unit_price * qty, 2)
        )
    else:
        item = POItem(description="שמרצף", quantity=1, unit_price=0, line_total=0)

    # סכומים (שורות נפרדות!)
    subtotal = re.search(r"0\.00 הנחה\s*\n\s*([\d,]+\.\d{2})", text)
    vat = re.search(r"מע.?מ\s*\n\s*([\d,]+\.\d{2})", text)
    total = re.search(r"סה.?כ מחיר כולל מע.?מ\s*\n\s*([\d,]+\.\d{2})", text)

    if subtotal:
        header["subtotal"] = normalize_amount(subtotal.group(1))
    if vat:
        header["vat"] = normalize_amount(vat.group(1))
    if total:
        header["total"] = normalize_amount(total.group(1))

    return customer_name, [item], header
