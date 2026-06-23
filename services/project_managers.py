from __future__ import annotations

import re
from pathlib import Path

from services.models import PurchaseOrderData
from services.parsers.common import (
    extract_text_pdfplumber,
    fix_hebrew_text,
    normalize_date,
)


FORBIDDEN_PHONES = {
    "0547720142",
    "0505204010",
    "0503011503",
    "547720142",
    "505204010",
    "503011503",
}

FORBIDDEN_NAME_TOKENS = (
    "בן יעקב",
    "אסף",
    "דודי",
    "אבא",
    "אמא",
    "משרד",
    "מפעל",
)

NEGATIVE_DOC_MARKERS = (
    "תעודת משלוח",
    "חולשמ תדועת",
    "חשבונית",
    "תעודת זיכוי",
    "קבלה",
    "invoice",
    "delivery note",
    "coc",
)

POSITIVE_DOC_MARKERS = (
    "הזמנת רכש",
    "שכר תנמזה",
    "מספר הזמנה",
    "הנמזה רפסמ",
    "מספר הזמ נה",
    "po",
)


def _normalize_ws(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _reverse_value(value: str) -> str:
    text = _normalize_ws((value or "")[::-1])
    text = text.replace("״", '"').replace("“", '"').replace("”", '"').replace("׳", "'")
    text = re.sub(r"\bבע.?במ\b", 'בע"מ', text)
    text = re.sub(r"\bבעמ\b", 'בע"מ', text)
    return text.strip(" -,:")


def _normalize_company(value: str) -> str:
    text = _normalize_ws(value)
    text = re.sub(r"^\s*לכבוד\s*:\s*", "", text)
    text = re.sub(r"^\s*לקוח\s*:\s*", "", text)
    text = re.sub(r"^\s*לקו\s*ח\s*:\s*", "", text)
    text = re.sub(r"\bלקו\s*ח\s*:\s*", "", text)
    text = re.sub(r"\bכתובת\s*:\s*", "", text)
    text = re.sub(r"\bאיש\s*קשר\s*:\s*", "", text)
    text = text.replace("פרוייקטים", "פרויקטים").replace("ייזום", "יזום")
    text = re.sub(r"\s+\d{8,10}$", "", text)
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", text):
        return ""
    if re.fullmatch(r"[\d/.\-]+", text):
        return ""
    if len(re.findall(r"\d", text)) >= max(4, len(text) // 3):
        return ""
    return text.strip(" -")


def _normalize_phone(value: str) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    if len(digits) == 9 and digits.startswith("5"):
        digits = f"0{digits}"
    if len(digits) != 10 or not digits.startswith("0"):
        return ""
    if digits in FORBIDDEN_PHONES:
        return ""
    return f"{digits[:3]}-{digits[3:]}"


def _normalize_tax_id(value: str) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    if len(digits) < 8 or len(digits) > 10:
        return ""
    if digits == "037017779":
        return ""
    return digits


def _sanitize_contact_name(value: str) -> str:
    text = _normalize_ws(value)
    text = re.sub(r"\bאיש\s*קשר\s*:\s*", "", text)
    if text.count(" ") >= 1:
        halves = text.split()
        if len(halves) % 2 == 0 and halves[: len(halves) // 2] == halves[len(halves) // 2 :]:
            text = " ".join(halves[: len(halves) // 2])
    text = text.strip(" -,:")
    if not text:
        return ""
    if any(token in text for token in FORBIDDEN_NAME_TOKENS):
        return ""
    if re.fullmatch(r"[\d\-\s]+", text):
        return ""
    if "טלפון" in text or "נייד" in text:
        return ""
    return text


def _normalize_site_address(value: str) -> str:
    text = _normalize_ws(value)
    if not text:
        return ""
    text = re.sub(r"\bכתובת\s*:\s*", "", text)
    text = re.sub(r"תאריך הדפסה.*$", "", text).strip(" -,")
    text = re.sub(r"\)\s*([^)]+)\s*\(", r"(\1)", text)
    parts = []
    for part in re.split(r"\s*,\s*|\s+\|\s+", text):
        clean = _normalize_ws(part).strip(" -,")
        if not clean:
            continue
        if clean not in parts:
            parts.append(clean)
    joined = ", ".join(parts)
    tokens = joined.split()
    if len(tokens) % 2 == 0 and tokens[: len(tokens) // 2] == tokens[len(tokens) // 2 :]:
        joined = " ".join(tokens[: len(tokens) // 2])
    return joined


def _is_purchase_order_document(pdf_path: Path, raw_text: str, fixed_text: str) -> bool:
    file_name = pdf_path.name.lower()
    raw_lower = (raw_text or "").lower()
    fixed_lower = (fixed_text or "").lower()

    if any(marker in file_name for marker in ("חשבונית", "תעודת משלוח", "receipt", "invoice", "delivery")):
        if not any(marker in file_name for marker in ("po", "הזמנת")):
            return False

    if any(marker in raw_lower or marker in fixed_lower for marker in NEGATIVE_DOC_MARKERS):
        if not any(marker in raw_lower or marker in fixed_lower for marker in POSITIVE_DOC_MARKERS):
            return False

    return any(marker in raw_lower or marker in fixed_lower for marker in POSITIVE_DOC_MARKERS)


def _raw_lines(raw_text: str) -> list[str]:
    return [line.strip() for line in (raw_text or "").splitlines() if _normalize_ws(line)]


def _extract_labeled_raw_value(lines: list[str], labels: tuple[str, ...]) -> tuple[str, int] | tuple[str, None]:
    for index, line in enumerate(lines):
        compact = _normalize_ws(line)
        for label in labels:
            pattern = re.compile(rf"^(?P<value>.+?)\s*:\s*{label}\s*$")
            match = pattern.search(compact)
            if match:
                return match.group("value").strip(), index
    return "", None


def _extract_company(raw_lines: list[str], folder_company: str) -> str:
    value, _ = _extract_labeled_raw_value(raw_lines, ("ח\\s*ו?קל", "דובכל"))
    company = _normalize_company(_reverse_value(value))
    return company or _normalize_company(folder_company)


def _extract_tax_id(raw_lines: list[str]) -> str:
    value, _ = _extract_labeled_raw_value(raw_lines, ("(?:\\.?סמ\\s*)?השרומ\\s*קסוע", "פ\\.ח"))
    return _normalize_tax_id(value)


def _extract_order_date(raw_lines: list[str]) -> str:
    value, _ = _extract_labeled_raw_value(raw_lines, ("הנמזה\\s*ךיראת", "ךיראת"))
    return normalize_date(value)


def _extract_address(raw_lines: list[str]) -> str:
    value, index = _extract_labeled_raw_value(raw_lines, ("תבותכ", "חולשמל\\s*תבותכ", "הקפסאל\\s*תבותכ"))
    if not value:
        return ""
    parts = [_reverse_value(value)]
    if index is not None:
        for next_line in raw_lines[index + 1 : index + 4]:
            compact = _normalize_ws(next_line)
            if ":" in compact:
                break
            if re.search(r"0\d[\d\-]{7,}", compact):
                break
            reversed_line = _reverse_value(compact)
            if not reversed_line or "תאריך" in reversed_line:
                continue
            parts.append(reversed_line)
    cleaned = []
    for part in parts:
        part = re.sub(r"תאריך הדפסה.*$", "", part).strip(" -,")
        if part and part not in cleaned:
            cleaned.append(part)
    return ", ".join(cleaned)


def _extract_contacts(raw_lines: list[str], customer_phone: str = "") -> list[tuple[str, str]]:
    contacts: list[tuple[str, str]] = []
    seen: set[str] = set()
    normalized_customer_phone = _normalize_phone(customer_phone)

    def add_contact(name: str, phone: str):
        clean_name = _sanitize_contact_name(name)
        clean_phone = _normalize_phone(phone)
        if not clean_phone or clean_phone == normalized_customer_phone or clean_phone in seen:
            return
        seen.add(clean_phone)
        contacts.append((clean_name, clean_phone))

    for index, line in enumerate(raw_lines):
        compact = _normalize_ws(line)

        match = re.search(r"^(?P<name>.+?)\s*:\s*רשק\s*שיא\s*$", compact)
        if match:
            name = _reverse_value(match.group("name"))
            phone = ""
            for nearby in raw_lines[index : index + 3]:
                phone_match = re.search(r"(?P<phone>0\d[\d\-]{7,})\s*:\s*ןופ\s*ל?ט", _normalize_ws(nearby))
                if phone_match:
                    phone = phone_match.group("phone")
                    break
            add_contact(name, phone)
            continue

        match = re.search(r"^(?P<phone>0\d[\d\-]{7,})\s*-\s*(?P<name>.+?)\s*$", compact)
        if match:
            add_contact(_reverse_value(match.group("name")), match.group("phone"))
            continue

        match = re.search(r"^(?P<name>.+?)\s*-\s*(?P<phone>0\d[\d\-]{7,})\s*$", compact)
        if match:
            add_contact(_reverse_value(match.group("name")), match.group("phone"))
            continue

        phone_match = re.search(r"(?P<phone>0\d[\d\-]{7,})\s*:\s*ןופ\s*ל?ט", compact)
        if phone_match:
            add_contact("", phone_match.group("phone"))

    return contacts


def _extract_item(raw_lines: list[str], parsed_po: PurchaseOrderData | None) -> str:
    if parsed_po and parsed_po.items:
        description = _normalize_ws(parsed_po.items[0].description)
        if description and description != "פריט לא זוהה":
            return description

    for line in raw_lines:
        compact = _normalize_ws(line)
        match = re.search(r"^(?P<value>.+?)\s*:\s*ט\s*ירפ\s*$", compact)
        if match:
            return _reverse_value(match.group("value"))
    return ""


def _extract_from_parsed_po(parsed_po: PurchaseOrderData | None) -> dict:
    if not parsed_po:
        return {}
    extra = parsed_po.extra or {}
    return {
        "company": _normalize_company(parsed_po.customer_name),
        "tax_id": _normalize_tax_id(parsed_po.customer_id),
        "site_address": _normalize_ws(parsed_po.delivery_address),
        "contact_name": _sanitize_contact_name(extra.get("contact_name") or parsed_po.contact_name or ""),
        "contact_phone": _normalize_phone(extra.get("contact_phone") or parsed_po.contact_phone or ""),
        "order_date": normalize_date(parsed_po.po_date),
        "item": _extract_item([], parsed_po),
    }


def extract_project_manager_entries_from_pdf(pdf_path: str | Path, parsed_po: PurchaseOrderData | None = None) -> list[dict]:
    pdf_path = Path(pdf_path)
    raw_text = extract_text_pdfplumber(pdf_path)
    fixed_text = fix_hebrew_text(raw_text)

    if not _is_purchase_order_document(pdf_path, raw_text, fixed_text):
        return []

    raw_lines = _raw_lines(raw_text)
    folder_company = pdf_path.parts[-3] if len(pdf_path.parts) >= 3 else ""

    parsed = _extract_from_parsed_po(parsed_po)
    company = _normalize_company(parsed.get("company") or "") or _extract_company(raw_lines, folder_company)
    if not company:
        company = _normalize_company(folder_company)
    site_address = _normalize_site_address(parsed.get("site_address") or "") or _normalize_site_address(_extract_address(raw_lines))
    order_date = parsed.get("order_date") or _extract_order_date(raw_lines)
    item = parsed.get("item") or _extract_item(raw_lines, parsed_po)
    tax_id = parsed.get("tax_id") or _extract_tax_id(raw_lines)

    contacts = _extract_contacts(raw_lines, customer_phone="")
    parsed_phone = parsed.get("contact_phone") or ""
    parsed_name = _sanitize_contact_name(parsed.get("contact_name") or "")
    if parsed_phone:
        contacts = [(name, phone) for name, phone in contacts if phone != parsed_phone] + [(parsed_name, parsed_phone)]

    # prefer named contact when same phone appears more than once
    by_phone: dict[str, tuple[str, str]] = {}
    for name, phone in contacts:
        current = by_phone.get(phone)
        if not current or (name and not current[0]):
            by_phone[phone] = (name, phone)

    rows = []
    for name, phone in by_phone.values():
        if not company or not site_address or not phone:
            continue
        rows.append(
            {
                "company": company,
                "tax_id": tax_id,
                "site_address": site_address,
                "contact_name": name,
                "order_date": order_date,
                "item": item,
                "contact_phone": phone,
            }
        )
    return rows


def rebuild_project_manager_entries_from_folder(root_dir: str | Path) -> list[dict]:
    root_path = Path(root_dir)
    rows: list[dict] = []
    seen_paths: set[Path] = set()
    for pdf_path in [*sorted(root_path.rglob("*.pdf")), *sorted(root_path.rglob("*.PDF"))]:
        if pdf_path in seen_paths:
            continue
        seen_paths.add(pdf_path)
        try:
            rows.extend(extract_project_manager_entries_from_pdf(pdf_path, parsed_po=None))
        except Exception:
            continue
    return rows
