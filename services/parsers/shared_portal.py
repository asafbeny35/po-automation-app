import re

from services.models import POItem
from services.parsers.common import fix_hebrew_text, normalize_date, normalize_po_number, normalize_ws, sanitize_contact_pair


def _rev(value: str) -> str:
    return (value or "").strip()[::-1]


def _rev_num(value: str):
    value = (value or "").strip()
    if not value:
        return None
    try:
        return float(value.replace(",", ""))
    except Exception:
        return None


def _fix_token(token: str) -> str:
    token = token.strip()
    if re.fullmatch(r"\d{2}/\d{2}/\d{2,4}", token):
        return token
    if re.fullmatch(r"[0-9./:-]+", token):
        return token[::-1]
    return token


def _fix_mixed_text(value: str) -> str:
    return " ".join(_fix_token(token) for token in (value or "").split())


def _clean_pdf_direction_marks(value: str) -> str:
    return re.sub(r"[\u200e\u200f\u202a-\u202e]", "", value or "")


def _parse_plain_number(value: str):
    value = normalize_ws(value or "").replace(",", "")
    if not value:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _parse_portal_number(value: str) -> float:
    raw = normalize_ws(value or "")
    if not raw:
        return 0.0

    candidates = []
    for candidate in {raw, raw[::-1]}:
        plain = _parse_plain_number(candidate)
        if plain is not None:
            candidates.append(plain)
        rev = _rev_num(candidate)
        if rev is not None:
            candidates.append(rev)

    positives = [number for number in candidates if number is not None and number > 0]
    if positives:
        return max(positives)
    return 0.0


def _fix_reversed_latin_tokens(value: str) -> str:
    tokens = []
    for token in normalize_ws(value).split():
        clean = token.strip("-")
        if re.fullmatch(r"[A-Z]{4,}", clean):
            reversed_clean = clean[::-1]
            if reversed_clean.isalpha():
                token = token.replace(clean, reversed_clean)
        tokens.append(token)
    return " ".join(tokens)


def _fix_date_yy(value: str) -> str:
    reversed_value = _rev(value)
    match = re.fullmatch(r"(\d{2})/(\d{2})/(\d{2})", reversed_value)
    if not match:
        return reversed_value
    return f"{match.group(1)}/{match.group(2)}/20{match.group(3)}"


def _extract_last_numbers(line: str, count: int = 3):
    numbers = re.findall(r"[0-9.,]+", line or "")
    return numbers[-count:] if len(numbers) >= count else []


def _detect_portal_unit(*segments: str) -> str:
    joined = " ".join(normalize_ws(segment or "") for segment in segments if segment)
    if not joined:
        return ""
    if re.search(r'מ["״]?ר|מטר מרובע|מטרים רבועים', joined):
        return 'מטר מרובע'
    if re.search(r"יח['׳]?|יחידה|יחידות", joined):
        return "יחידה"
    if "גליל" in joined or "גלילים" in joined:
        return "גלילים"
    return ""


def _extract_contact_names(flat: str) -> list[str]:
    names = []
    for raw in re.findall(r"([^0-9:\n][^:\n]+?)\s*:ידיל", flat):
        clean = normalize_ws(raw[::-1])
        if clean:
            names.append(clean)
    for raw in re.findall(r"([^0-9:\n][^:\n]+?)\s*:רשק שיא", flat):
        clean = normalize_ws(raw[::-1])
        if clean:
            names.append(clean)
    return names


def _extract_contact_phones(flat: str, customer_phone: str) -> list[str]:
    phones = []
    for raw in re.findall(r"([0-9\-]+)\s*:\s*(?:ןופלט|דיינ ןופלט)", flat):
        clean = raw
        if clean and clean != customer_phone:
            phones.append(clean)
    for raw in re.findall(r"(0\d{1,2}-\d{7})", flat):
        if raw and raw != customer_phone:
            phones.append(raw)
    mobile_phones = [phone for phone in phones if phone.startswith("05")]
    return mobile_phones or phones


def _extract_delivery_address(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        if "ליטסקט תונורתפ" not in line and "טקסטיל" not in line:
            continue
        before_supplier = line.split("ליטסקט תונורתפ", 1)[0].strip()
        if "טקסטיל" in line and "בן יעקב" in line:
            before_supplier = line.split("בן יעקב", 1)[0].strip()

        candidates = []
        if before_supplier:
            candidates.append(_fix_mixed_text(before_supplier[::-1]))

        for extra in lines[index + 1:index + 3]:
            value = extra.replace("34 ןרוגה", "").replace("תילתע", "").strip()
            value = _fix_mixed_text(value[::-1]).strip(" -,")
            if value:
                candidates.append(value)

        address = ", ".join(part for part in candidates if part and "הגורן" not in part and "עתלית" not in part)
        if address:
            return normalize_ws(address)
    return ""


def _extract_delivery_block(lines: list[str], customer_phone: str = "") -> tuple[str, str, str]:
    for index, raw_line in enumerate(lines):
        line = normalize_ws(_clean_pdf_direction_marks(raw_line))
        if "ליטסקט תונורתפ" not in line and "טקסטיל" not in line:
            continue

        before_supplier = line
        if "ליטסקט תונורתפ" in before_supplier:
            before_supplier = before_supplier.split("ליטסקט תונורתפ", 1)[0].strip()
        if "בן יעקב" in before_supplier:
            before_supplier = before_supplier.split("בן יעקב", 1)[0].strip()

        address_parts = []
        if before_supplier:
            candidate = _fix_mixed_text(before_supplier[::-1]).strip(" -,")
            if candidate:
                address_parts.append(candidate)

        contacts = []
        for extra_raw in lines[index + 1:index + 5]:
            extra = normalize_ws(_clean_pdf_direction_marks(extra_raw))
            if not extra:
                continue

            extra_fixed = _fix_mixed_text(extra[::-1]).strip(" -,")
            phone_match = re.search(r"(05\d[- ]?\d{7}|0\d{1,2}-\d{7})", extra_fixed)
            if phone_match:
                phone = normalize_ws(phone_match.group(1)).replace(" ", "")
                name = normalize_ws(extra_fixed.replace(phone_match.group(1), "").strip(" -,:"))
                contacts.append((name, phone))
                continue

            if "הגורן" in extra_fixed or "עתלית" in extra_fixed:
                continue
            if extra_fixed:
                address_parts.append(extra_fixed)

        address = normalize_ws(", ".join(part for part in address_parts if part))
        contact_name = ""
        contact_phone = ""
        for name, phone in contacts:
            clean_name, clean_phone = sanitize_contact_pair(name, phone, customer_phone=customer_phone)
            if clean_name or clean_phone:
                contact_name = clean_name
                contact_phone = clean_phone
                break

        return address, contact_name, contact_phone

    return "", "", ""


def _extract_portal_contact_from_details(lines: list[str], customer_phone: str = "") -> tuple[str, str]:
    candidates: list[tuple[str, str]] = []

    for raw_line in lines:
        line = normalize_ws(_clean_pdf_direction_marks(raw_line))
        if not line:
            continue

        details_match = re.search(r"(05\d[- ]?\d{7})\s+([א-ת\"'׳\-\s]+)\s*:םיטרפ", line)
        if details_match:
            phone = normalize_ws(details_match.group(1)).replace(" ", "")
            name = normalize_ws(details_match.group(2)[::-1])
            candidates.append((name, phone))

        details_hyphen_match = re.search(r"(05\d[- ]?\d{7,8})-([א-ת\"'׳\-\s]+)\s*:םיטרפ", line)
        if details_hyphen_match:
            phone = normalize_ws(details_hyphen_match.group(1)).replace(" ", "")
            name = normalize_ws(details_hyphen_match.group(2)[::-1])
            candidates.append((name, phone))

        for raw_name in re.findall(r"([א-ת\"'׳\-\s]+)\s*:ידיל", line):
            name = normalize_ws(raw_name[::-1])
            if name:
                candidates.append((name, ""))

    best_name = ""
    best_phone = ""
    for name, phone in candidates:
        clean_name, clean_phone = sanitize_contact_pair(name, phone, customer_phone=customer_phone)
        if clean_name and clean_phone:
            return clean_name, clean_phone
        if clean_phone and not best_phone:
            best_phone = clean_phone
        if clean_name and len(clean_name) > len(best_name):
            best_name = clean_name

    best_name, best_phone = sanitize_contact_pair(best_name, best_phone, customer_phone=customer_phone)
    return best_name, best_phone


def _clean_portal_description_segment(segment: str, project: str = "") -> str:
    tokens = normalize_ws(segment).split()
    if not tokens:
        return "פריט לא זוהה"

    project_words = {word for word in normalize_ws(project).split() if len(word) > 1}

    if any(re.fullmatch(r"\d{2}/\d{2}/\d{2,4}", token) for token in tokens):
        date_index = next(i for i, token in enumerate(tokens) if re.fullmatch(r"\d{2}/\d{2}/\d{2,4}", token))
        prefix = tokens[:date_index]
        suffix = []
        skipping = True
        for token in tokens[date_index + 1:]:
            if skipping and (
                re.fullmatch(r"\d+", token)
                or token in project_words
                or token.replace('"', "").replace("״", "") in project_words
            ):
                continue
            skipping = False
            suffix.append(token)
        tokens = prefix + suffix

    if project_words:
        for index, token in enumerate(tokens):
            if token in project_words:
                trailing_gloss = [tail for tail in tokens[index:] if "לגליל" in tail or "גליל" in tail]
                tokens = tokens[:index] + trailing_gloss
                break

    while tokens:
        tail = tokens[-1]
        normalized_tail = tail.replace("*", "").strip()
        if (
            re.fullmatch(r"\d+", normalized_tail)
            or re.fullmatch(r"[A-Z]{2,}\d+", normalized_tail)
            or re.fullmatch(r"\d+[A-Z]{1,4}", normalized_tail)
            or re.fullmatch(r"[A-Z]{1,4}\d+[A-Z]{0,4}", normalized_tail)
            or normalized_tail in project_words
        ):
            tokens.pop()
            continue
        break

    description = normalize_ws(" ".join(tokens)).strip(" -,")
    description = re.sub(r"\b(?:PR\d+|\d+[A-Z]{1,4}|[A-Z]{1,4}\d+[A-Z]{0,4})\b", "", description)
    description = description.replace(")2", "(2").replace(")1", "(1")
    description = description.replace("לגליל(", "לגליל)")
    if "לגליל" in description and description.endswith("גלילים"):
        description = re.sub(r"\s+גלילים$", "", description)
    description = normalize_ws(description).strip(" -,")
    return description or "פריט לא זוהה"


def _extract_items(lines: list[str], fixed_lines: list[str], project: str = "") -> list[POItem]:
    items: list[POItem] = []

    item_lines = []
    for raw_line in lines:
        line = normalize_ws(_clean_pdf_direction_marks(raw_line))
        if not any(char.isdigit() for char in line):
            continue
        if (
            re.search(r"\d{2}/\d{2}/\d{2,4}", line) and re.search(r"\d{6,12}", line)
        ) or (
            re.search(r"\d{6,12}", line) and "ח" in line and re.search(r"\d{1,3}(?:,\d{3})*\.\d{2}", line)
        ):
            item_lines.append(line)

    for line in item_lines:
        simple_units_match = re.search(
            r"([0-9.,]+)\s+ח\"?ש\s+([0-9.,]+)\s+\S+\s+([0-9.,]+)\s+(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s+(\d{6,12})\s+\d+$",
            line,
        )
        if simple_units_match:
            line_total = _parse_portal_number(simple_units_match.group(1))
            unit_price = _parse_portal_number(simple_units_match.group(2))
            quantity = _parse_portal_number(simple_units_match.group(3))
            description = _fix_mixed_text(simple_units_match.group(5)[::-1]).strip()
            description = _clean_portal_description_segment(description, project=project)
            sku = simple_units_match.group(6).strip()
            items.append(
                POItem(
                    sku=sku,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                    unit=_detect_portal_unit(line, description),
                )
            )
            continue

        normal_prefix_match = re.search(
            r"^\s*([0-9.,]+)\s+([0-9.,]+)\S*\s+([0-9.,]+)\S*\s+([0-9.,]+)\S*\s+(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s*$",
            line,
        )
        if normal_prefix_match:
            line_total = _rev_num(normal_prefix_match.group(1)) or 0
            unit_price = _rev_num(normal_prefix_match.group(2)) or 0
            quantity = _rev_num(normal_prefix_match.group(4)) or 0
            trailing = (normal_prefix_match.group(6) or "").strip()

            trailing = re.sub(r"\s+\d+\s*$", "", trailing).strip()
            sku_match = re.match(r"(\d{6,12})(.*)$", trailing)
            sku = sku_match.group(1).strip() if sku_match else ""
            description = (sku_match.group(2) if sku_match else trailing).strip()
            if sku:
                description = description.strip(" -")
            description = normalize_ws(description).strip() or "פריט לא זוהה"
            items.append(
                POItem(
                    sku=sku,
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                    unit=_detect_portal_unit(line, description),
                )
            )
            continue

        match = re.search(
            r"([0-9.,]+)\s+ח.?ש\s+([0-9.,]+)\s+\S+\s+([0-9.,]+)\s+\S+\s+\d{2}/\d{2}/\d{2}\s+(.+?)\s+(\d{6,12})\s+\d+$",
            line,
        )
        if match:
            line_total = _rev_num(match.group(1)) or 0
            unit_price = _rev_num(match.group(2)) or 0
            quantity = _rev_num(match.group(3)) or 0
            description = _fix_mixed_text(match.group(4)[::-1]).strip() or "פריט לא זוהה"
            sku = match.group(5)[::-1]
            items.append(
                POItem(
                    sku=sku or "",
                    description=description,
                    quantity=quantity,
                    unit_price=unit_price,
                    line_total=line_total,
                    unit=_detect_portal_unit(line, description),
                )
            )
            continue

        compact_portal_match = re.search(
            r"^\s*([0-9,]+\.\d{2})\s+\S+\s+([0-9,]+\.\d{2})\s+\S+\s+([0-9,]+\.\d{2})\s+(.+?)\s+(\d{6,12})\s+\d+\s*$",
            line,
        )
        if compact_portal_match:
            line_total = _parse_plain_number(compact_portal_match.group(1)) or 0
            unit_price = _parse_plain_number(compact_portal_match.group(2)) or 0
            quantity = _parse_plain_number(compact_portal_match.group(3)) or 0
            description_segment = normalize_ws(compact_portal_match.group(4))
            sku = compact_portal_match.group(5).strip()

            description = _fix_mixed_text(description_segment[::-1]).strip(" -,")
            description = normalize_ws(description).strip(" -,") or "פריט לא זוהה"

            items.append(
                POItem(
                    sku=sku,
                    description=description,
                    quantity=quantity or 1,
                    unit_price=unit_price,
                    line_total=line_total,
                    unit=_detect_portal_unit(line, description),
                )
            )

    if items:
        deduped: list[POItem] = []
        seen: set[tuple[str, str, float, float, float]] = set()
        for item in items:
            key = (
                normalize_ws(str(item.sku or "")),
                normalize_ws(str(item.description or "")),
                float(item.quantity or 0),
                float(item.unit_price or 0),
                float(item.line_total or 0),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    for index, raw_line in enumerate(fixed_lines):
        line = normalize_ws(_clean_pdf_direction_marks(raw_line))
        if "*" not in line or "ש\"ח" not in line or not re.search(r"\d{5,12}", line):
            continue

        match = re.search(
            r"^\d+\s+(\d{5,12})\s+\*\d{5,12}\*\s+(.+?)\s+([0-9.,]+)\s+מ\S+\s+([0-9.,]+)\s+מ\S+\s+([0-9.,]+)\s+ש\"?ח\s+([0-9.,]+)$",
            line,
        )
        if not match:
            continue

        sku = match.group(1).strip()
        description_segment = match.group(2).strip()
        continuation_text = ""
        next_line = normalize_ws(_clean_pdf_direction_marks(fixed_lines[index + 1])) if index + 1 < len(fixed_lines) else ""
        if next_line and ("לגליל" in next_line or "גליל" in next_line):
            description_segment = f"{description_segment} {next_line}"
            continuation_text = next_line
        elif next_line and not re.match(r"^\d+", next_line):
            continuation_parts = [next_line]
            if index + 2 < len(fixed_lines):
                next_next_line = normalize_ws(_clean_pdf_direction_marks(fixed_lines[index + 2]))
                if next_next_line and not re.match(r"^\d+", next_next_line) and not re.search(r"\d{6,12}", next_next_line):
                    continuation_parts.append(next_next_line)
            continuation_text = " ".join(continuation_parts)
            description_segment = f"{description_segment} {continuation_text}"

        description = _clean_portal_description_segment(description_segment, project=project)
        if continuation_text and (description in {"פריט לא זוהה", "גלילים", "לגליל", "לגליל)"} or len(description) < 8):
            description = _clean_portal_description_segment(continuation_text, project=project)
        quantity = _parse_portal_number(match.group(4))
        unit_price = _parse_portal_number(match.group(5))
        line_total = _parse_portal_number(match.group(6))

        return [
            POItem(
                sku=sku,
                description=description,
                quantity=quantity,
                unit_price=unit_price,
                line_total=line_total,
                unit=_detect_portal_unit(line, description, continuation_text),
            )
        ]

    return [POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0)]


def _extract_item_from_fixed_text(text: str) -> POItem:
    cleaned_text = normalize_ws(_clean_pdf_direction_marks(text))
    item = POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0)

    match = re.search(
        r"([0-9.,]+)\s+ש\"?ח\s+([0-9.,]+)\s+מ[\"']?ר\s+([0-9.,]+)\s+מ[\"']?ר\s+(\d{2}/\d{2}/\d{2,4})\s+(\d{6,12})\s+(.+?)\s+(\d+)",
        cleaned_text,
    )
    if match:
        line_total = _rev_num(match.group(1)) or _rev_num(match.group(1)[::-1]) or 0
        unit_price = _rev_num(match.group(2)) or _rev_num(match.group(2)[::-1]) or 0
        quantity = _rev_num(match.group(3)) or _rev_num(match.group(3)[::-1]) or 0
        sku = match.group(5).strip()
        description = normalize_ws(match.group(6)).strip(" -") or "פריט לא זוהה"
        return POItem(
            sku=sku,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
            unit=_detect_portal_unit(cleaned_text, description),
        )

    match = re.search(
        r"(\d{6,12})\s+(.+?)\s+(\d{2}/\d{2}/\d{2,4})\s+([0-9.,]+)\s+\S+\s+([0-9.,]+)\s+\S+\s+([0-9.,]+)\s+ש\"?ח\s+([0-9.,]+)",
        cleaned_text,
    )
    if match:
        sku = match.group(1).strip()
        description = normalize_ws(match.group(2)).strip(" -") or "פריט לא זוהה"
        quantity = _rev_num(match.group(5)) or 0
        unit_price = _rev_num(match.group(6)) or 0
        line_total = _rev_num(match.group(7)) or 0
        return POItem(
            sku=sku,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
            unit=_detect_portal_unit(cleaned_text, description),
        )

    return item


def _extract_item_from_fixed_lines(lines: list[str]) -> POItem:
    item = POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0)
    for raw_line in lines:
        line = normalize_ws(_clean_pdf_direction_marks(raw_line))
        if not line or not re.search(r"\d{2}/\d{2}/\d{2,4}", line) or not re.search(r"\d{6,12}", line):
            continue

        match = re.search(
            r"^\s*([0-9,]+\.\d{2})\s+([0-9,]+\.\d{2})\S*\s+([0-9,]+\.\d{2})\S*\s+([0-9,]+\.\d{2})\S*\s+(\d{2}/\d{2}/\d{2,4})\s+(.+?)\s*$",
            line,
        )
        if not match:
            continue

        trailing = match.group(6).strip()
        trailing = re.sub(r"\s+\d+\s*$", "", trailing).strip()
        sku_match = re.match(r"(\d{6,12})(.*)$", trailing)
        if not sku_match:
            continue

        sku = sku_match.group(1).strip()
        description = normalize_ws(_fix_reversed_latin_tokens(sku_match.group(2).strip(" -"))) or "פריט לא זוהה"
        line_total = _parse_plain_number(match.group(1)) or 0
        unit_price = _parse_plain_number(match.group(2)) or 0
        quantity = _parse_plain_number(match.group(4)) or 0

        return POItem(
            sku=sku,
            description=description,
            quantity=quantity,
            unit_price=unit_price,
            line_total=line_total,
            unit=_detect_portal_unit(line, description),
        )

    cleaned_lines = [normalize_ws(_clean_pdf_direction_marks(line)) for line in lines if normalize_ws(_clean_pdf_direction_marks(line))]
    for index, line in enumerate(cleaned_lines):
        if "רצומ רואת" not in line:
            continue

        description_line = cleaned_lines[index + 1] if index + 1 < len(cleaned_lines) else ""
        quantity_line = ""
        unit_price_line = ""
        line_total_line = ""

        for probe_index in range(index + 1, min(len(cleaned_lines), index + 20)):
            probe = cleaned_lines[probe_index]
            if not quantity_line and "תומכ" in probe and probe_index + 1 < len(cleaned_lines):
                quantity_line = cleaned_lines[probe_index + 1]
            if not unit_price_line and "הדיחיל ריחמ" in probe and probe_index + 1 < len(cleaned_lines):
                unit_price_line = cleaned_lines[probe_index + 1]
            if "ריחמ כ\"הס" in probe and probe_index + 1 < len(cleaned_lines):
                line_total_line = cleaned_lines[probe_index + 1]
                break

        sku_match = re.search(r"(\d{8,12})\s*$", description_line)
        sku = sku_match.group(1)[::-1] if sku_match else ""
        description_raw = description_line[:sku_match.start()].strip() if sku_match else description_line.strip()
        description = normalize_ws(fix_hebrew_text(description_raw)).strip(" -,") or "פריט לא זוהה"

        quantity_match = re.search(r"([0-9]+(?:\.[0-9]+)?)", quantity_line)
        unit_price_match = re.search(r"([0-9,]+(?:\.[0-9]+)?)", unit_price_line)
        line_total_match = re.search(r"([0-9,]+(?:\.[0-9]+)?)", line_total_line)

        if description != "פריט לא זוהה" and (quantity_match or unit_price_match or line_total_match):
            quantity = _parse_plain_number(quantity_match.group(1)) if quantity_match else 0
            unit_price = _parse_plain_number(unit_price_match.group(1)) if unit_price_match else 0
            line_total = _parse_plain_number(line_total_match.group(1)) if line_total_match else 0
            return POItem(
                sku=sku,
                description=description,
                quantity=quantity or 1,
                unit_price=unit_price or 0,
                line_total=line_total or 0,
                unit=_detect_portal_unit(quantity_line, description_line, description),
            )

    return item


def parse_portal_purchase_order(text: str, customer_name: str):
    if "רפסמ שכר תנמזה" not in text and "הזמנת רכש" not in text:
        return None

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    flat = "\n".join(lines)
    fixed_text = fix_hebrew_text(text)
    fixed_lines = [line.strip() for line in fixed_text.splitlines() if line.strip()]

    header = {
        "customer_email": "",
        "customer_id": "",
        "po_number": "",
        "po_date": "",
        "subtotal": None,
        "vat": None,
        "total": None,
        "payment_terms_days": None,
        "payment_terms_label": "",
        "project": "",
        "delivery_address": "",
        "contact_name": "",
        "contact_phone": "",
        "customer_phone": "",
    }

    match = re.search(r"([0-9]{9})\s*:\s*השרומ קסוע", flat)
    if match:
        header["customer_id"] = match.group(1)

    phone_matches = re.findall(r"([0-9\-]+)\s*:\s*(?:ןופלט|דיינ ןופלט)", flat)
    if phone_matches:
        header["customer_phone"] = phone_matches[0]

    match = re.search(r"([A-Za-z0-9\-/]+)\s+רפסמ שכר תנמזה", flat)
    if match:
        header["po_number"] = normalize_po_number(match.group(1)[::-1] if match.group(1).endswith("OP") else match.group(1))

    match = re.search(r"([0-9/]{8})\s*:\s*הנמזה ךיראת", flat)
    if match:
        date_value = match.group(1)
        header["po_date"] = normalize_date(date_value[::-1] if date_value.startswith("6") else date_value)

    delivery_address, delivery_contact_name, delivery_contact_phone = _extract_delivery_block(
        lines,
        customer_phone=header["customer_phone"],
    )
    header["delivery_address"] = delivery_address or _extract_delivery_address(lines)
    header["delivery_address"] = re.sub(r"תאריך הדפסה[:\s]*[0-9/: ]+", "", header["delivery_address"]).strip(" ,")
    header["delivery_address"] = re.sub(r"^הגורן\s*43\s*,?\s*עתלית\s*\d*\s*", "", header["delivery_address"]).strip(" ,")
    header["delivery_address"] = re.sub(r"הזמנת רכש מספר\s+\S+.*$", "", header["delivery_address"]).strip(" ,")

    embedded_contact = re.search(r"(?:^|,)\s*(?:\d{5,7}\s+)?([א-ת\"׳\-\s]+?)\s*-\s*(05\d[- ]?\d{7})", header["delivery_address"])
    if embedded_contact:
        embedded_name = normalize_ws(embedded_contact.group(1))
        embedded_phone = normalize_ws(embedded_contact.group(2)).replace(" ", "")
        contact_name, contact_phone = sanitize_contact_pair(
            embedded_name,
            embedded_phone,
            customer_phone=header["customer_phone"],
        )
        if contact_name or contact_phone:
            delivery_contact_name = delivery_contact_name or contact_name
            delivery_contact_phone = delivery_contact_phone or contact_phone
        header["delivery_address"] = normalize_ws(
            re.sub(r"(?:^|,)\s*(?:\d{5,7}\s+)?[א-ת\"׳\-\s]+?\s*-\s*05\d[- ]?\d{7}.*$", "", header["delivery_address"])
        ).strip(" ,")

    match = re.search(r"([^\n]+)\s*:\s*טקיורפ", flat)
    if match:
        project = _fix_mixed_text(match.group(1)[::-1]).strip()
        if project and "כמות" not in project and "מחיר" not in project and "תאור" not in project:
            header["project"] = project

    if not header["delivery_address"] or header["delivery_address"].startswith("לידי:"):
        header["delivery_address"] = header["project"] or header["delivery_address"]

    contact_names = _extract_contact_names(flat)
    contact_phones = _extract_contact_phones(flat, customer_phone=header["customer_phone"])

    contact_name = contact_names[-1] if contact_names else ""
    contact_phone = contact_phones[-1] if contact_phones else ""
    contact_name, contact_phone = sanitize_contact_pair(
        contact_name,
        contact_phone,
        customer_phone=header["customer_phone"],
    )
    details_contact_name, details_contact_phone = _extract_portal_contact_from_details(lines, customer_phone=header["customer_phone"])
    header["contact_name"] = delivery_contact_name or details_contact_name or contact_name
    header["contact_phone"] = delivery_contact_phone or details_contact_phone or contact_phone

    match = re.search(r"(\d+)ש\s*:\s*םולשת יאנת", flat)
    if match:
        days = int(match.group(1))
        header["payment_terms_days"] = days
        header["payment_terms_label"] = f"שוטף + {days}"

    items = _extract_items(lines, fixed_lines, project=header["project"])
    first_item = items[0] if items else POItem(description="פריט לא זוהה", quantity=1, unit_price=0, line_total=0)
    if first_item.description == "פריט לא זוהה" and not first_item.sku and float(first_item.quantity or 0) == 1 and float(first_item.unit_price or 0) == 0:
        first_item = _extract_item_from_fixed_lines(fixed_lines)
        items = [first_item]
    if first_item.description == "פריט לא זוהה" and not first_item.sku and float(first_item.quantity or 0) == 1 and float(first_item.unit_price or 0) == 0:
        first_item = _extract_item_from_fixed_text(fixed_text)
        items = [first_item]

    match = re.search(r"([0-9.,]+)\s+ללוכ ריחמ", flat)
    if match:
        header["subtotal"] = _rev_num(match.group(1))

    vat_line = next((line for line in lines if "מע" in line and "%" in line), "")
    vat_match = re.findall(r"[0-9.,]+", vat_line)
    if vat_match:
        header["vat"] = _rev_num(vat_match[-1])

    match = re.search(r"([0-9.,]+)\s+ריחמ כ\"?הס", flat)
    if match:
        header["total"] = _rev_num(match.group(1))

    if header["subtotal"] is None:
        header["subtotal"] = round(sum(float(item.line_total or 0) for item in items), 2)
    if header["vat"] is None and header["subtotal"] is not None:
        header["vat"] = round(header["subtotal"] * 0.18, 2)
    if header["total"] is None and header["subtotal"] is not None and header["vat"] is not None:
        header["total"] = round(header["subtotal"] + header["vat"], 2)

    return customer_name, items, header
