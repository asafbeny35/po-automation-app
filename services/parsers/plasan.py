
import re
from services.models import POItem

VAT_RATE = 0.18


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def _extract_description(text: str) -> str:
    lines = [line.rstrip() for line in (text or "").splitlines()]
    capture = False
    description_lines: list[str] = []

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if capture and description_lines:
                continue
            continue

        if not capture and re.search(r"\bPolymers?\s*-", line, re.I):
            capture = True
            line = re.sub(r"^\d[\d,]*\.\d+\s+\d[\d,]*\.\d+\s+", "", line).strip()
            line = re.sub(r"\s+\d{1,3}\s+\d{10,}-\d{2}\s+\d+\s*$", "", line).strip()
            if line:
                description_lines.append(line)
            continue

        if not capture:
            continue

        if any(marker in line for marker in (":ןרצי ט\"קמ", ":ןרצי ט''קמ", "תוכיא תושירד יכמסמ", "תומכ הדיחי", "כ\"הס", "כ'הס")):
            break

        if re.search(r"\d+\s+Square\s*meter", line, re.I):
            break

        description_lines.append(line)

    return _clean(" ".join(description_lines))


def parse(text: str):
    print("🔥 RAW TEXT START")
    print(text[:2000])
    print("🔥 RAW TEXT END")

    data = {
        "customer_name": 'פלסן סאסא בע"מ',
        "customer_id": "513768341",
        "customer_phone": "",
        "customer_email": "",
        "delivery_address": "פלסן סאסא, קיבוץ סאסא",
        "po_number": "",
        "po_date": "",
        "subtotal": 0.0,
        "vat": 0.0,
        "total": 0.0,
        "items": [],
        "extra": {
            "project": "",
            "contact_name": "",
            "contact_phone": "",
            "footer_text": "",
        },
    }

    # PO number
    patterns = [
        r"הזמנת רכש מספר\s*(\d+)",
        r"Purchase Order No\.?\s*(\d+)",
        r"\b(\d{7})\b",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            data["po_number"] = "PO" + m.group(1)
            break

    # Contact name = buyer
    m = re.search(r"([A-Za-z]+,\s*[A-Za-z]+)\s*:\s*קניין", text)
    if m:
        data["extra"]["contact_name"] = _clean(m.group(1))
    else:
        data["extra"]["contact_name"] = "Hazan, Ohad"

    # Contact phone
    m = re.search(r"נייד[:\s]*([0-9\-]{9,})", text)
    if m:
        data["extra"]["contact_phone"] = _clean(m.group(1))
    else:
        data["extra"]["contact_phone"] = "052-6991246"

    # Email
    m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', text)
    if m:
        data["customer_email"] = _clean(m.group(1))

    # Date extraction
    m = re.search(r"(\d{1,2})[\-\s]([A-Za-z]{3,9})[\-\s](\d{4})", text)
    if m:
        day, month_str, year = m.groups()
        months = {
            "jan": "01", "january": "01",
            "feb": "02", "february": "02",
            "mar": "03", "march": "03",
            "apr": "04", "april": "04",
            "may": "05",
            "jun": "06", "june": "06",
            "jul": "07", "july": "07",
            "aug": "08", "august": "08",
            "sep": "09", "september": "09",
            "oct": "10", "october": "10",
            "nov": "11", "november": "11",
            "dec": "12", "december": "12",
        }
        month = months.get(month_str.lower()[:3], "")
        if month:
            data["po_date"] = f"{int(day):02d}/{month}/{year}"
    # Project
    m = re.search(r"מס[\'\"״׳]?\s*פרוייקט:\s*([0-9]+)", text)
    if m:
        data["extra"]["project"] = _clean(m.group(1))

    # SKU
    m = re.search(r"\b(\d{10,}-\d{2})\b", text)
    sku = m.group(1) if m else ""

    # Quantities
    quantities = re.findall(r"(\d+(?:\.\d+)?)\s+Square\s*meter", text, re.I)
    total_qty = sum(float(q) for q in quantities) if quantities else 0.0

    # Unit price
    unit_price = 0.0
    m = re.search(r"(\d+\.\d{3})\s+Polymer", text)
    if m:
        unit_price = float(m.group(1))
    if not unit_price:
        m = re.search(r"\b(\d+\.\d{3})\b", text)
        if m:
            unit_price = float(m.group(1))

    # Totals
    if total_qty > 0 and unit_price > 0:
        subtotal = round(unit_price * total_qty, 2)
        vat = round(subtotal * VAT_RATE, 2)
        total = round(subtotal + vat, 2)
        data["subtotal"] = subtotal
        data["vat"] = vat
        data["total"] = total

    # Description for invoice / delivery
    description = _extract_description(text)

    # Item
    if total_qty > 0:
        item = POItem(
            description=description,
            quantity=total_qty,
            unit_price=unit_price,
            line_total=data["subtotal"],
            sku=sku or None,
        )
        data["items"].append(item)

    # Mirror contact fields to top-level for common parser compatibility
    data["contact_name"] = data["extra"].get("contact_name", "")
    data["contact_phone"] = data["extra"].get("contact_phone", "")
    data["project"] = data["extra"].get("project", "")
    data["footer_text"] = data["extra"].get("footer_text", "")

    # Footer
    footer_parts = []
    if data["po_number"]:
        footer_parts.append(f"הזמנת רכש {data['po_number']}")
    if data["extra"]["project"]:
        footer_parts.append(f"פרויקט: {data['extra']['project']}")
    if data["delivery_address"]:
        footer_parts.append(f"כתובת לאספקה: {data['delivery_address']}")
    if data["extra"]["contact_name"]:
        footer_parts.append(f"איש קשר: {data['extra']['contact_name']}")
    if data["extra"]["contact_phone"]:
        footer_parts.append(f"טל': {data['extra']['contact_phone']}")
    data["extra"]["footer_text"] = " | ".join(footer_parts)

    return data
