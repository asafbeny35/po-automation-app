import re

from services.models import POItem
from services.parsers.common import fix_hebrew_text, to_purchase_order


def _rev(value: str) -> str:
    return (value or "").strip()[::-1]


def _rev_amount(value: str) -> float:
    value = (value or "").strip().replace("₪", "")
    if not value:
        return 0.0
    return float(_rev(value).replace(",", ""))


def _clean(value: str) -> str:
    return " ".join((value or "").split()).strip()


def _extract_project(fixed_text: str) -> str:
    m = re.search(r"פרויקט\s+(.+?)\s+-\s+הזמנה מס'", fixed_text)
    if m:
        return m.group(1).replace("TXEN", "NEXT").strip()
    return ""


def _extract_customer(raw_text: str, fixed_text: str) -> tuple[str, str]:
    raw_match = re.search(
        r"\((\d{9})\s+\.פ\.ח\)\s+(.+?)\s+:\s*רובע\s+קיפהל\s+שי\s+תינובשח",
        raw_text,
    )
    if raw_match:
        customer_id = raw_match.group(1).strip()
        customer_name = raw_match.group(2)[::-1].replace("ORP", "PRO").strip()
        return customer_name, customer_id

    m = re.search(r"\*\*\*\s*חשבונית יש להפיק עבור:\s*(.+?)\s+\)ח\.פ\.\s*([0-9]{9})\(", fixed_text)
    if not m:
        return "", ""
    name = m.group(1).replace("ORP", "PRO").strip()
    customer_id = m.group(2).strip()
    if customer_id and customer_id[::-1] in raw_text:
        customer_id = customer_id[::-1]
    return name, customer_id


def _extract_contacts(fixed_text: str) -> tuple[str, str]:
    m = re.search(r"טל:\s*([^,\n]+)\s+([0-9\-]+),\s*([^,\n]+)\s+([0-9\-]+)", fixed_text)
    if m:
        n1, p1, n2, p2 = m.groups()
        return f"{n1.strip()} / {n2.strip()}", f"{_rev(p1)} / {_rev(p2)}"

    m = re.search(r"איש קשר:\s*([^0-9\n]+)\s+([0-9\-]{10,})", fixed_text)
    if m:
        return m.group(1).strip(), _rev(m.group(2))

    m = re.search(r"איש קשר:\s*([^\n]+)", fixed_text)
    if m:
        return m.group(1).strip(), ""

    return "", ""


def _extract_delivery_address(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        if "הגורן 43" not in line:
            continue
        remainder = line.split("הגורן 43", 1)[-1].strip()
        if remainder:
            remainder = _clean(re.sub(r"\)\s*מתחם ה\s*(\d+)\(", lambda m: f"(מתחם ה {m.group(1)[::-1]})", remainder))
            remainder = re.sub(r"\b(\d{2})\b", lambda m: m.group(1)[::-1] if m.group(1).startswith("0") or m.group(1).endswith("1") else m.group(1), remainder)
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        city = next_line.split("נייד:", 1)[-1] if "נייד:" in next_line else next_line
        city = _clean(re.sub(r"[0-9:\-]+", "", city))
        city = city.replace("עתלית", "").strip()
        parts = [part for part in [remainder, city] if part]
        if parts:
            return ", ".join(parts)
    return ""


def _extract_item(fixed_text: str) -> POItem | None:
    block_match = re.search(r"ק2ו1דlebaLRQ תאור י\"מ לתאריך\s+(.+?)\s+תנאי תשלום:", fixed_text, re.DOTALL)
    if not block_match:
        return None
    block = _clean(block_match.group(1))

    sku_match = re.search(r"([A-Z0-9]+)-", block)
    if not sku_match:
        return None
    sku = _rev(sku_match.group(1))

    if 'מ"ר' in block:
        m = re.search(rf"{re.escape(sku_match.group(1))}-\s+(.+?)\s+מ\"ר\s+([0-9.]+)\s+([0-9.,]+)\s+([0-9.,]+)", block)
    else:
        m = re.search(rf"{re.escape(sku_match.group(1))}-\s+(.+?)\s+יח['״]?\s+([0-9.]+)\s+([0-9.,]+)\s+([0-9.,]+)", block)
    if not m:
        return None

    description = _clean(m.group(1)).replace("TXEN", "NEXT")
    quantity = _rev_amount(m.group(2))
    unit_price = _rev_amount(m.group(3))
    line_total = _rev_amount(m.group(4))

    if sku == "QTP5555":
        mm_match = re.search(r"\n([0-9]{2})\s+מ\"מ\s+לבידוד צינורות", fixed_text)
        if mm_match:
            description = f"{description} {_rev(mm_match.group(1))} מ\"מ לבידוד צינורות"

    return POItem(
        description=description,
        quantity=quantity,
        unit_price=unit_price,
        line_total=line_total,
        sku=sku,
    )


def parse_sivanb(text: str):
    print("👉 ENTERED SIVANB")

    if ":ח וקל" in text and ":רתא/תבותכ" in text:
        raw_lines = [line.strip() for line in text.splitlines() if line.strip()]
        flat_raw = "\n".join(raw_lines)

        customer_match = re.search(r"([0-9]{9})\s+פ\.ח\s*-\s*(.+?)\s*:\s*ח וקל", flat_raw)
        address_match = re.search(r"(.+?)\s*:\s*רתא/תבותכ", flat_raw)
        contact1 = re.search(r"([0-9\-]+)\s+(.+?)\s*:\s*1 רשק שיא", flat_raw)
        contact2 = re.search(r"([0-9\-]+)\s+(.+?)\s*:\s*2 רשק שיא", flat_raw)
        po_match = re.search(r"([0-9/]+)\s*:\s*הנ ?מזה רפסמ", flat_raw)
        item_match = re.search(r"(.+?)\s*:\s*ט ?ירפ", flat_raw)
        qty_match = re.search(r"(?:׳?חי\s+)?([0-9.]+)\s*\n:תו ?מכ", flat_raw)
        sku_match = re.search(r"([A-Z0-9]+)\s+ט.?קמ", flat_raw)

        customer_name = customer_match.group(2)[::-1].strip() if customer_match else "סיון ביצוע"
        delivery_address = address_match.group(1)[::-1].strip() if address_match else ""
        if contact1 and contact2:
            contact_name = f"{contact1.group(2)[::-1].strip()} / {contact2.group(2)[::-1].strip()}"
            contact_phone = f"{contact1.group(1)} / {contact2.group(1)}"
        elif contact1:
            contact_name = contact1.group(2)[::-1].strip()
            contact_phone = contact1.group(1)
        else:
            contact_name = ""
            contact_phone = ""

        item = POItem(
            description=item_match.group(1)[::-1].strip() if item_match else "פריט לא זוהה",
            quantity=float(qty_match.group(1)) if qty_match else 1.0,
            unit_price=0,
            line_total=0,
            sku=sku_match.group(1) if sku_match else "",
        )
        header = {
            "po_number": po_match.group(1) if po_match else "",
            "po_date": "",
            "customer_id": customer_match.group(1) if customer_match else "",
            "customer_phone": "",
            "delivery_address": delivery_address,
            "subtotal": 0,
            "vat": 0,
            "total": 0,
            "payment_terms_days": None,
            "payment_terms_label": "",
            "project": "",
            "contact_name": contact_name,
            "contact_phone": contact_phone,
        }
        return to_purchase_order(customer_name, [item], header, text)

    needs_fix = any(marker in text for marker in ("טקיורפ", ":רובע", "ק2ו1ד", "ףטוש", "רוקמ -"))
    fixed_text = fix_hebrew_text(text) if needs_fix else text
    if not any(marker in fixed_text for marker in ("NEXT", "PROD5050", "QTP5555", "חשבונית יש להפיק עבור:")):
        return None

    lines = [line.strip() for line in fixed_text.splitlines() if line.strip()]
    flat = "\n".join(lines)

    po_number = ""
    raw_po_match = re.search(r"([0-9]{3,}/[0-9]{3,})\s+'?סמ הנמזה", text)
    if not raw_po_match:
        raw_po_match = re.search(r"([0-9]{3,}/[0-9]{3,})\s*:?הנמזה רפסמ", text)
    if raw_po_match:
        po_number = raw_po_match.group(1).strip()
    else:
        m = re.search(r"הזמנה מס'\s*([0-9/]+)", flat)
        if m:
            po_number = m.group(1)

    po_date = ""
    m = re.search(r"\b\d{2}/\d{2}/\d{4}\b", flat)
    if m:
        po_date = m.group(0)

    payment_days = None
    m = re.search(r"שוטף\+?([0-9]+)", flat)
    if m:
        payment_days = int(_rev(m.group(1)))

    customer_name, customer_id = _extract_customer(text, flat)
    project = _extract_project(flat)
    contact_name, contact_phone = _extract_contacts(flat)
    delivery_address = _extract_delivery_address(lines)
    item = _extract_item(flat)
    if not item:
        return None

    subtotal_match = re.search(r"סה\"כ הזמנה:([0-9.,]+)", flat)
    subtotal = _rev_amount(subtotal_match.group(1)) if subtotal_match else item.line_total

    header = {
        "po_number": po_number,
        "po_date": po_date,
        "customer_id": customer_id,
        "customer_phone": "",
        "delivery_address": delivery_address,
        "subtotal": subtotal,
        "vat": round(subtotal * 0.18, 2),
        "total": round(subtotal * 1.18, 2),
        "payment_terms_days": payment_days,
        "payment_terms_label": f"שוטף + {payment_days}" if payment_days is not None else "",
        "project": project,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
    }

    return to_purchase_order(customer_name, [item], header, text)
