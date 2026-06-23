import re

from services.models import POItem
from services.parsers.common import normalize_date, normalize_ws, sanitize_contact_pair


CUSTOMER_NAME = 'סלע ביצוע בע"מ'


def _clean_text(text: str) -> str:
    return re.sub(r"[\u200e\u200f\u202a-\u202e]", "", text or "").replace("\r", "\n")


def _normalize_amount(value: str) -> float:
    raw = normalize_ws(value).replace(",", "").replace("₪", "").replace('ש"ח', "").replace("שח", "").strip()
    raw = re.sub(r"[^\d.]", "", raw)
    try:
        return float(raw) if raw else 0.0
    except Exception:
        return 0.0


def _restore_reversed_line(line: str) -> str:
    tokens = line.split()
    if not tokens:
        return ""
    restored_tokens = []
    for token in reversed(tokens):
        if re.search(r"[א-ת]", token):
            token = token[::-1]
        restored_tokens.append(token)
    restored = " ".join(restored_tokens)
    restored = re.sub(r"\s+,", ",", restored)
    restored = re.sub(r"\s+:", ":", restored)
    return normalize_ws(restored)


def _normalize_source_text(text: str) -> str:
    cleaned = _clean_text(text)
    restored_lines = [_restore_reversed_line(line) for line in cleaned.splitlines()]
    return "\n".join(line for line in restored_lines if normalize_ws(line))


def _extract_project(text: str) -> str:
    match = re.search(r"פרויקט:\s*([^\n]+)", text)
    return normalize_ws(match.group(1)) if match else ""


def _extract_delivery_and_contacts(lines: list[str], customer_phone: str) -> tuple[str, str, str, str, str]:
    buyer_name = ""
    buyer_phone = ""
    site_name = ""
    site_phone = ""
    delivery_address = ""

    for index, line in enumerate(lines):
        if "כתובת למשלוח:" not in line:
            continue

        line_after = normalize_ws(lines[index + 1]) if index + 1 < len(lines) else ""
        line_two = normalize_ws(lines[index + 2]) if index + 2 < len(lines) else ""
        line_three = normalize_ws(lines[index + 3]) if index + 3 < len(lines) else ""
        line_four = normalize_ws(lines[index + 4]) if index + 4 < len(lines) else ""

        names = re.findall(r"לידי:\s*([^:]+?)(?=\s+לידי:|$)", line_four)
        names = [normalize_ws(name) for name in names if normalize_ws(name)]
        if names:
            buyer_name = names[0]
        if len(names) > 1:
            site_name = names[1]

        phones = re.findall(r"(05\d{8}|0\d{1,2}-\d{7})", line_five := normalize_ws(lines[index + 5]) if index + 5 < len(lines) else "")
        phones = [normalize_ws(phone) for phone in phones if normalize_ws(phone)]
        if phones:
            buyer_phone = phones[0]
        if len(phones) > 1:
            site_phone = phones[-1]

        street_candidates = re.findall(r"[א-ת\"'׳״\-]+(?:\s+[א-ת\"'׳״\-]+)*\s+\d+[א-ת]?", line_two)
        site_street = normalize_ws(street_candidates[-1]) if street_candidates else ""

        site_city = ""
        if line_three:
            if " " in line_three:
                site_city = normalize_ws(line_three.split(" ", 1)[1])
            else:
                site_city = line_three

        if site_street or site_city:
            delivery_address = normalize_ws(", ".join(part for part in [site_street, site_city] if part))
        break

    clean_site_name, clean_site_phone = sanitize_contact_pair(site_name, site_phone, customer_phone=customer_phone)
    return (
        delivery_address,
        clean_site_name,
        clean_site_phone,
        normalize_ws(buyer_name),
        normalize_ws(buyer_phone),
    )


def _extract_payment_days(text: str) -> int | None:
    match = re.search(r"תנאי תשלום:\s*ש(\d+)", text)
    if not match:
        return None
    token = match.group(1).strip()
    if not token:
        return None
    try:
        return int(token[::-1])
    except Exception:
        return None


def _extract_items(text: str, project: str) -> list[dict]:
    items: list[dict] = []
    qty_pattern = re.compile(
        r"\s+([0-9.,]+)\s+יח'\s+([0-9.,]+)\s+יח'\s+([0-9.,]+)\s+ש\"ח\s+([0-9.,]+)$"
    )

    for raw_line in text.splitlines():
        line = normalize_ws(raw_line)
        if not line or not re.match(r"^\d+\s+\d{6,12}\s+", line):
            continue

        base_match = re.match(r"^(\d+)\s+(\d{6,12})\s+(.+)$", line)
        if not base_match:
            continue
        tail_match = qty_pattern.search(line)
        if not tail_match:
            continue

        row_number = int(base_match.group(1))
        sku = normalize_ws(base_match.group(2))
        middle = normalize_ws(base_match.group(3))
        quantity = _normalize_amount(tail_match.group(1))
        unit_price = _normalize_amount(tail_match.group(3))
        line_total = _normalize_amount(tail_match.group(4))

        body = normalize_ws(line[line.find(sku) + len(sku) : tail_match.start()])
        project_value = project if project and project in body else ""
        supplier_sku = ""
        description = ""

        if project_value:
            before_project = normalize_ws(body[: body.rfind(project_value)])
            if before_project:
                parts = before_project.split()
                supplier_sku = parts[-1] if parts else ""
                description = normalize_ws(before_project[: before_project.rfind(supplier_sku)] if supplier_sku else before_project)

        if not project_value:
            pieces = body.split()
            if len(pieces) >= 2:
                supplier_sku = pieces[-1]
                description = normalize_ws(" ".join(pieces[:-1]))
            else:
                description = body

        if not description:
            description = "פריט לא זוהה"

        description = normalize_ws(description).strip(" -,")
        supplier_sku = normalize_ws(supplier_sku)

        item = {
            "row_number": row_number,
            "sku": sku,
            "description": description or "פריט לא זוהה",
            "supplier_sku": supplier_sku,
            "project": project_value,
            "quantity": quantity,
            "unit_price": unit_price,
            "line_total": line_total,
        }
        items.append(item)

    items.sort(key=lambda item: item["row_number"])
    return items


def parse(text: str):
    if "PO260" not in text and "הזמנת רכש" not in text and "עוציב עלס" not in text:
        return None

    source_text = _normalize_source_text(text)
    if "סלע ביצוע" not in source_text or "הזמנת רכש מספר" not in source_text:
        return None

    lines = [normalize_ws(line) for line in source_text.splitlines() if normalize_ws(line)]

    po_number_match = re.search(r"הזמנת רכש מספר\s*(\S+)", source_text)
    po_number = po_number_match.group(1).strip() if po_number_match else ""

    po_date_match = re.search(r"תאריך הזמנה:\s*([0-9/]{8})", source_text)
    po_date = normalize_date(po_date_match.group(1)) if po_date_match else ""

    vat_file_match = re.search(r"מספר תיק במע[\"״]מ[:\s]*([0-9]{9})", source_text)
    if not vat_file_match:
        vat_file_match = re.search(r"([0-9]{9})\s*:מספר תיק במע[\"״]מ", source_text)
    if not vat_file_match:
        vat_file_match = re.search(r"([0-9]{9})\s+באיחוד עוסקים מספר\s+מדווח לצרכי מע[\"״]מ", source_text)

    customer_id_match = re.search(r"עוסק מורשה:\s*(\d{9})", source_text)
    if not customer_id_match:
        customer_id_match = re.search(r"([0-9]{9})\s*:עוסק מורשה", source_text)

    customer_id = (
        vat_file_match.group(1)
        if vat_file_match
        else (customer_id_match.group(1) if customer_id_match else "")
    )

    customer_phone_match = re.search(r"טלפון:\s*,?(0\d[\d-]+)", source_text)
    customer_phone = normalize_ws(customer_phone_match.group(1)) if customer_phone_match else ""

    project = _extract_project(source_text)
    delivery_address, contact_name, contact_phone, buyer_name, buyer_phone = _extract_delivery_and_contacts(
        lines,
        customer_phone=customer_phone,
    )

    subtotal_match = re.search(r"מחיר כולל\s*([0-9.,]+)", source_text)
    subtotal = _normalize_amount(subtotal_match.group(1)) if subtotal_match else 0.0

    vat_match = re.search(r"מע\"מ\s*\([0-9.,%]+\)\s*([0-9.,]+)", source_text)
    vat = _normalize_amount(vat_match.group(1)) if vat_match else 0.0

    total_match = re.search(r"סה\"כ מחיר\s*([0-9.,]+)\s*ש\"ח", source_text)
    total = _normalize_amount(total_match.group(1)) if total_match else 0.0

    supplier_number_match = re.search(r"מס' ספק:\s*(\d+)", source_text)
    supplier_number = supplier_number_match.group(1) if supplier_number_match else ""

    payment_terms_days = _extract_payment_days(source_text)
    payment_terms_label = f"שוטף + {payment_terms_days}" if payment_terms_days is not None else ""

    parsed_items = _extract_items(source_text, project)
    items = [
        POItem(
            description=item["description"],
            sku=item["sku"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            line_total=item["line_total"],
            unit="יחידה",
        )
        for item in parsed_items
    ]

    header = {
        "customer_id": customer_id,
        "customer_phone": customer_phone,
        "customer_email": "",
        "delivery_address": delivery_address,
        "po_number": po_number,
        "po_date": po_date,
        "subtotal": subtotal,
        "vat": vat,
        "total": total,
        "project": project,
        "contact_name": contact_name,
        "contact_phone": contact_phone,
        "payment_terms_days": payment_terms_days,
        "payment_terms_label": payment_terms_label,
    }

    header["extra"] = {
        "supplier_number": supplier_number,
        "buyer_contact_name": buyer_name,
        "buyer_contact_phone": buyer_phone,
        "supplier_sku_map": {item["sku"]: item["supplier_sku"] for item in parsed_items if item.get("sku")},
        "items_json": parsed_items,
    }

    return CUSTOMER_NAME, items, header
