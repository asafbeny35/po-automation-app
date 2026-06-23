import re
from services.models import POItem
from services.parsers.common import common_fields, first_match, normalize_amount, normalize_ws

def parse_prashkovsky(text: str):
    header = common_fields(text)
    customer_name = 'פרשקובסקי PRO'
    item = parse_generic_item(text)
    return customer_name, [item], header

def parse_generic_item(text: str) -> POItem:
    qp = re.search(
        r"(.{0,30}QuietPipe.{0,80})\s+1\s+([\d.,]+)\s+מ[\"״]?ר\s+₪?([\d.,]+)\s+([\d.,]+)",
        text,
        re.MULTILINE | re.DOTALL | re.IGNORECASE,
    )
    if qp:
        desc = normalize_ws(qp.group(1))
        qty = normalize_amount(qp.group(2)) or 1
        unit_price = normalize_amount(qp.group(3)) or 0
        line_total = normalize_amount(qp.group(4)) or round(qty * unit_price, 2)
        return POItem(description=desc, quantity=qty, unit_price=unit_price, line_total=line_total)

    m = re.search(
        r"\d+\s+(\d+)\s+(.+?)\s+\d{2}/\d{2}/\d{2,4}\s+([\d.,]+)\s+\S+\s+([\d.,]+)\s+(?:ש[\"']?ח|₪)\s+([\d.,]+)",
        text,
        re.MULTILINE | re.DOTALL,
    )
    if m:
        return POItem(
            sku=m.group(1),
            description=normalize_ws(m.group(2)),
            quantity=normalize_amount(m.group(3)) or 1,
            unit_price=normalize_amount(m.group(4)) or 0,
            line_total=normalize_amount(m.group(5)) or 0,
        )

    m = re.search(r"כל אחד\s+([\d.,]+)\s+([\d.,]+)\s+(.+?)(?:\n|$)", text, re.MULTILINE)
    if m:
        return POItem(
            description=normalize_ws(m.group(3)),
            quantity=normalize_amount(m.group(2)) or 1,
            unit_price=normalize_amount(m.group(1)) or 0,
            line_total=round((normalize_amount(m.group(1)) or 0) * (normalize_amount(m.group(2)) or 1), 2),
        )

    desc = (
        first_match(r"תיאור מוצר[:\s]*([^\n]+)", text)
        or first_match(r"תיאור פריט[:\s]*([^\n]+)", text)
        or "פריט לא זוהה"
    )
    qty = normalize_amount(first_match(r"כמות[:\s]*([\d.,]+)", text)) or 1
    unit_price = normalize_amount(first_match(r"מחיר ליחידה[:\s₪]*([\d.,]+)", text)) or 0
    line_total = normalize_amount(first_match(r"סה[\"״]?כ לשורה[:\s₪]*([\ד.,]+)", text)) or round(qty * unit_price, 2)

    return POItem(description=normalize_ws(desc), quantity=qty, unit_price=unit_price, line_total=line_total)

def parse_generic(text: str):
    header = common_fields(text)

    customer_name = (
        first_match(r"יעד ההזמנה:\s*([^\n]+)", text)
        or first_match(r"לכבוד:\s*\n([^\n]+)", text, flags=re.MULTILINE)
        or first_match(r"^([^\n]+בע\"מ)", text, flags=re.MULTILINE)
        or ""
    )
    customer_name = normalize_ws(customer_name)

    item = parse_generic_item(text)
    return customer_name, [item], header
