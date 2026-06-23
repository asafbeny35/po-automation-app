from __future__ import annotations

import base64
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html import unescape
from pathlib import Path
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

from .gmail_oauth import _gmail_service
from .google_drive_sync import ensure_child_folder, ensure_file_in_folder, managed_storage_root_folder_id
from .google_sheets import get_cached_pazomat_rows, load_pazomat_rows, save_pazomat_rows
from .runtime_paths import runtime_root


PAZOMAT_OUTPUT_DIR = runtime_root() / "output" / "pazomat_sync"
PAZOMAT_DRIVE_ROOT_TITLE = "מסמכי מנהלה"
PAZOMAT_DRIVE_FOLDER_TITLE = "פזומט"
PAZOMAT_EXPECTED_START = date(2025, 4, 1)
_BIDI_CHARS = "\u202a\u202b\u202c\u202d\u202e\u200f\u200e\ufeff"
_ATTACHMENT_NAME_SAFE = re.compile(r"[^A-Za-z0-9._() \-\u0590-\u05FF]+")


def _month_key(dt: date) -> str:
    return dt.strftime("%m/%Y")


def expected_months() -> list[str]:
    current = PAZOMAT_EXPECTED_START
    expected_end = date.today().replace(day=1)
    months: list[str] = []
    while current <= expected_end:
        months.append(_month_key(current))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months


def _next_month_start(day_value: date) -> date:
    if day_value.month == 12:
        return date(day_value.year + 1, 1, 1)
    return date(day_value.year, day_value.month + 1, 1)


def _pazomat_query() -> str:
    after_day = PAZOMAT_EXPECTED_START - timedelta(days=1)
    before_day = _next_month_start(date.today())
    return f"from:oper@pazomat.co.il after:{after_day.strftime('%Y/%m/%d')} before:{before_day.strftime('%Y/%m/%d')}"


def _month_sort_value(label: str) -> tuple[int, int]:
    raw = str(label or "").strip()
    try:
        month_text, year_text = raw.split("/", 1)
        return int(year_text), int(month_text)
    except Exception:
        return (9999, 99)


def _filter_rows_for_year(rows: list[dict], year: int) -> list[dict]:
    suffix = f"/{year}"
    filtered = [row for row in rows if str(row.get("month") or "").strip().endswith(suffix)]
    return sorted(filtered, key=lambda row: _month_sort_value(str(row.get("month") or "")))


def _drive_folder_view_link(folder_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{folder_id}"


def _drive_file_view_link(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view?usp=drivesdk"


def ensure_pazomat_drive_folder() -> tuple[str, str]:
    parent_id = ensure_child_folder(managed_storage_root_folder_id(), PAZOMAT_DRIVE_ROOT_TITLE)
    folder_id = ensure_child_folder(parent_id, PAZOMAT_DRIVE_FOLDER_TITLE)
    return folder_id, _drive_folder_view_link(folder_id)


def _message_headers(payload: dict) -> dict[str, str]:
    return {
        str(item.get("name") or "").lower(): str(item.get("value") or "")
        for item in (payload.get("headers") or [])
    }


def _walk_parts(parts: list[dict] | None):
    for part in parts or []:
        yield part
        yield from _walk_parts(part.get("parts") or [])


def _extract_month_from_subject(subject: str) -> str:
    match = re.search(r"(\d{2}/\d{4})", str(subject or ""))
    return match.group(1) if match else ""


def _decode_gmail_attachment_data(data: str) -> bytes:
    raw = str(data or "").strip()
    padded = raw + "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _safe_attachment_name(name: str, month: str) -> str:
    base_name = _ATTACHMENT_NAME_SAFE.sub("_", str(name or "").strip()).strip("._ ") or "invoice.pdf"
    return f"{month.replace('/', '-') }__{base_name}".replace(" ", "_")


def _decode_gmail_body(data: str) -> str:
    raw = str(data or "").strip()
    if not raw:
        return ""
    padded = raw + "=" * ((4 - len(raw) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_html_from_payload(payload: dict | None) -> str:
    if not isinstance(payload, dict):
        return ""
    mime_type = str(payload.get("mimeType") or "").lower()
    body = payload.get("body") or {}
    if mime_type == "text/html":
        return _decode_gmail_body(body.get("data") or "")
    for part in payload.get("parts") or []:
        html_text = _extract_html_from_payload(part)
        if html_text.strip():
            return html_text
    return ""


def _extract_document_link_from_html(html_text: str) -> str:
    raw = str(html_text or "")
    if not raw:
        return ""
    def _clean_ws(value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "")).strip()
    anchors = re.findall(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", raw, flags=re.IGNORECASE | re.DOTALL)
    normalized_candidates: list[tuple[str, str]] = []
    for href, label_html in anchors:
        label = re.sub(r"<[^>]+>", " ", str(label_html or ""))
        label = _clean_ws(unescape(label))
        normalized_candidates.append((str(href or "").strip(), label))
    preferred = (
        "קישור לצפייה במסמכים",
        "צפייה במסמכים",
        "חשבוניות",
        "דוחות",
    )
    for href, label in normalized_candidates:
        if any(token in label for token in preferred):
            return href
    for href, _label in normalized_candidates:
        lowered = href.lower()
        if "fuelpic" in lowered or "invoice_summary_" in lowered or "sendgrid.net/ls/click" in lowered:
            return href
    return normalized_candidates[0][0] if normalized_candidates else ""


def _extract_month_from_filename(name: str) -> str:
    text = str(name or "")
    match = re.search(r"invoice_summary_(\d{2})_(\d{4})", text, re.IGNORECASE)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    match = re.search(r"(\d{2})-(\d{4})__", text)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return ""


def _local_pdf_candidates() -> dict[str, Path]:
    expected = set(expected_months())
    candidates: dict[str, Path] = {}
    search_roots = [
        PAZOMAT_OUTPUT_DIR,
        Path("/Users/asafbeny/Downloads"),
    ]
    for root in search_roots:
        if not root.exists():
            continue
        for path in root.glob("*.pdf"):
            month = _extract_month_from_filename(path.name)
            if month not in expected:
                continue
            existing = candidates.get(month)
            if existing is None or path.stat().st_mtime > existing.stat().st_mtime:
                candidates[month] = path
    return candidates


def _materialize_local_pdf(source: Path, month: str) -> Path | None:
    if not source.exists():
        return None
    PAZOMAT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = PAZOMAT_OUTPUT_DIR / _safe_attachment_name(source.name, month)
    if source.resolve() != target.resolve():
        target.write_bytes(source.read_bytes())
    return target


def _normalize_pdf_text(text: str) -> list[str]:
    cleaned = text.translate({ord(ch): None for ch in _BIDI_CHARS})
    lines = [re.sub(r"\s+", " ", line).strip() for line in cleaned.splitlines()]
    return [line for line in lines if line]


def _run_pdftotext(file_path: Path) -> list[str]:
    try:
        output = subprocess.check_output(
            ["pdftotext", "-layout", str(file_path), "-"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return _normalize_pdf_text(output)
    except Exception:
        pass
    try:
        output = subprocess.check_output(
            ["pdftotext", str(file_path), "-"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
        return _normalize_pdf_text(output)
    except Exception:
        pass
    # pdftotext not available (e.g. Vercel) — fall back to pdfplumber
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(str(file_path)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return _normalize_pdf_text("\n".join(pages))
    except Exception:
        return []


def _parse_amount_from_line(line: str) -> str:
    match = re.match(r"([\d,]+\.\d{2,3})", str(line or "").strip())
    return match.group(1).replace(",", "") if match else ""


def _format_money(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}"


def _format_liters(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.3f}"


@dataclass
class PazomatPdfParseResult:
    invoice_number: str = ""
    fuel_doc_number: str = ""
    total_amount: str = ""
    fuel_amount: str = ""
    service_amount: str = ""
    debit_date: str = ""
    vehicle_count: str = ""
    vehicles_json: str = "[]"
    card_count: str = ""
    cards_json: str = "[]"
    liters_total: str = ""


def parse_pazomat_invoice(pdf_path: Path) -> PazomatPdfParseResult:
    lines = _run_pdftotext(pdf_path)
    service_amount = ""
    fuel_amount = ""
    total_amount = ""
    invoice_number = ""
    fuel_doc_number = ""
    debit_date = ""
    vehicles: list[str] = []
    cards: list[str] = []
    liters_total = 0.0

    for line in lines:
        if not invoice_number and "חשבונית מס" in line:
            match = re.search(r"חשבונית מס(?:״? מספר)?\s+(\d{5,})", line)
            if match:
                invoice_number = match.group(1)
        if not fuel_doc_number and ("מסמך אחר" in line or "ריכוז מוצרי דלק מס" in line):
            match = re.search(r"(?:מסמך אחר״? מספר|ריכוז מוצרי דלק מס)\s+(\d{5,})", line)
            if match:
                fuel_doc_number = match.group(1)
        if not service_amount and "חיובים בגין מוצרים" in line:
            service_amount = _parse_amount_from_line(line)
        if not fuel_amount and "חיובים בגין מוצרי דלק" in line:
            fuel_amount = _parse_amount_from_line(line)
        if not total_amount and "ס ה ״כ" in line and "חיובים" not in line and "כ ל לי" not in line:
            maybe_total = _parse_amount_from_line(line)
            if maybe_total:
                total_amount = maybe_total
        if not debit_date and "בתאריך" in line and "סך" in line:
            match = re.search(r"בתאריך\s+(\d{2}/\d{2}/\d{4})", line)
            if match:
                debit_date = match.group(1)

        vehicle_match = re.search(r"([\d,]+\.\d{3})\s+בנזין.*?(\d{7,8})\s*$", line)
        if vehicle_match:
            liters_total += float(vehicle_match.group(1).replace(",", ""))
            vehicles.append(vehicle_match.group(2))

        cards.extend(re.findall(r"\b(\d{13})\b", line))

    unique_vehicles = sorted({value for value in vehicles if value})
    unique_cards = sorted({value for value in cards if value})
    liters_total_value = liters_total if liters_total > 0 else None

    return PazomatPdfParseResult(
        invoice_number=invoice_number,
        fuel_doc_number=fuel_doc_number,
        total_amount=total_amount,
        fuel_amount=fuel_amount,
        service_amount=service_amount,
        debit_date=debit_date,
        vehicle_count=str(len(unique_vehicles)) if unique_vehicles else "",
        vehicles_json=json.dumps(unique_vehicles, ensure_ascii=False),
        card_count=str(len(unique_cards)) if unique_cards else "",
        cards_json=json.dumps(unique_cards, ensure_ascii=False),
        liters_total=_format_liters(liters_total_value),
    )


def _gmail_message_candidates() -> dict[str, dict]:
    service = _gmail_service()
    response = service.users().messages().list(userId="me", q=_pazomat_query(), maxResults=200).execute()
    messages = response.get("messages") or []
    candidates: dict[str, dict] = {}

    for item in messages:
        message_id = str(item.get("id") or "").strip()
        if not message_id:
            continue
        message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        payload = message.get("payload") or {}
        headers = _message_headers(payload)
        subject = headers.get("subject", "")
        month = _extract_month_from_subject(subject)
        if month not in expected_months():
            continue
        html_body = _extract_html_from_payload(payload)
        document_link = _extract_document_link_from_html(html_body)
        pdf_parts = []
        for part in _walk_parts(payload.get("parts") or []):
            filename = str(part.get("filename") or "").strip()
            attachment_id = str((part.get("body") or {}).get("attachmentId") or "").strip()
            if filename.lower().endswith(".pdf") and attachment_id:
                pdf_parts.append(
                    {
                        "filename": filename,
                        "attachment_id": attachment_id,
                    }
                )
        candidate = {
            "month": month,
            "message_id": message_id,
            "subject": subject,
            "internal_date": int(str(message.get("internalDate") or "0") or 0),
            "pdf_parts": pdf_parts,
            "document_link": document_link,
        }
        existing = candidates.get(month)
        if not existing:
            candidates[month] = candidate
            continue
        existing_has_pdf = bool(existing.get("pdf_parts"))
        current_has_pdf = bool(pdf_parts)
        if current_has_pdf and not existing_has_pdf:
            candidates[month] = candidate
            continue
        existing_has_link = bool(str(existing.get("document_link") or "").strip())
        current_has_link = bool(document_link)
        if current_has_link and not existing_has_link:
            candidates[month] = candidate
            continue
        if current_has_pdf == existing_has_pdf and candidate["internal_date"] > int(existing.get("internal_date") or 0):
            candidates[month] = candidate
    return candidates


def _download_month_pdf(service, month: str, message_id: str, pdf_parts: list[dict]) -> Path | None:
    if not pdf_parts:
        return None
    PAZOMAT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    part = pdf_parts[0]
    attachment = service.users().messages().attachments().get(
        userId="me",
        messageId=message_id,
        id=str(part.get("attachment_id") or ""),
    ).execute()
    raw = _decode_gmail_attachment_data(attachment.get("data", ""))
    target = PAZOMAT_OUTPUT_DIR / _safe_attachment_name(str(part.get("filename") or "invoice.pdf"), month)
    target.write_bytes(raw)
    return target


def _download_month_pdf_from_link(document_link: str, month: str) -> Path | None:
    raw_link = str(document_link or "").strip()
    if not raw_link:
        return None
    try:
        request = Request(raw_link, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=60) as response:
            final_url = str(response.geturl() or raw_link)
            payload = response.read()
            content_type = str(response.headers.get("Content-Type") or "").lower()
    except Exception:
        return None
    if not payload:
        return None
    if not payload.startswith(b"%PDF") and "pdf" not in content_type:
        return None
    parsed = urlparse(final_url)
    final_name = Path(unquote(parsed.path or "")).name or "invoice.pdf"
    target_name = _safe_attachment_name(final_name, month)
    PAZOMAT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = PAZOMAT_OUTPUT_DIR / target_name
    target.write_bytes(payload)
    return target


def _row_note_for_status(status: str, month: str) -> str:
    if status == "pdf_available":
        return "נמצאה חשבונית PDF והועלתה ל-Drive."
    if status == "pdf_link_available":
        return "נמצא קישור להורדת החשבונית מהמייל, הקובץ הורד והועלה ל-Drive."
    if status == "email_only":
        return f"נמצא מייל עבור {month}, אבל לא נמצאה חשבונית PDF usable כצרופה."
    return f"לא נמצא כרגע מייל של פזומט עבור {month}."


def refresh_pazomat_rows() -> list[dict]:
    expected = expected_months()
    service = _gmail_service()
    candidates = _gmail_message_candidates()
    local_candidates = _local_pdf_candidates()
    drive_folder_id, drive_folder_url = ensure_pazomat_drive_folder()
    rows: list[dict] = []

    for month in expected:
        candidate = candidates.get(month)
        row = {
            "month": month,
            "status": "missing",
            "gmail_message_id": "",
            "subject": "",
            "source_type": "missing",
            "invoice_number": "",
            "fuel_doc_number": "",
            "total_amount": "",
            "fuel_amount": "",
            "service_amount": "",
            "debit_date": "",
            "vehicle_count": "",
            "vehicles_json": "[]",
            "card_count": "",
            "cards_json": "[]",
            "liters_total": "",
            "drive_folder_id": drive_folder_id,
            "drive_folder_url": drive_folder_url,
            "drive_file_id": "",
            "drive_url": "",
            "local_path": "",
            "notes": _row_note_for_status("missing", month),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        local_pdf_source = local_candidates.get(month)
        if not candidate:
            if local_pdf_source and local_pdf_source.exists():
                local_pdf = _materialize_local_pdf(local_pdf_source, month)
                parse_result = parse_pazomat_invoice(local_pdf) if local_pdf and local_pdf.exists() else PazomatPdfParseResult()
                uploaded = ensure_file_in_folder(drive_folder_id, local_pdf, drive_name=local_pdf.name) if local_pdf and local_pdf.exists() else None
                row.update(
                    {
                        "status": "pdf_available",
                        "source_type": "manual_pdf",
                        "invoice_number": parse_result.invoice_number,
                        "fuel_doc_number": parse_result.fuel_doc_number,
                        "total_amount": parse_result.total_amount,
                        "fuel_amount": parse_result.fuel_amount,
                        "service_amount": parse_result.service_amount,
                        "debit_date": parse_result.debit_date,
                        "vehicle_count": parse_result.vehicle_count,
                        "vehicles_json": parse_result.vehicles_json,
                        "card_count": parse_result.card_count,
                        "cards_json": parse_result.cards_json,
                        "liters_total": parse_result.liters_total,
                        "drive_file_id": str((uploaded or {}).get("id") or ""),
                        "drive_url": str((uploaded or {}).get("web_view_link") or "") or _drive_file_view_link(str((uploaded or {}).get("id") or "")) if uploaded else "",
                        "local_path": str(local_pdf or ""),
                        "notes": "החשבונית הוזנה ידנית מקובץ שסופק והועלתה ל-Drive.",
                        "updated_at": datetime.now().isoformat(timespec="seconds"),
                    }
                )
            rows.append(row)
            continue

        row["gmail_message_id"] = str(candidate.get("message_id") or "")
        row["subject"] = str(candidate.get("subject") or "")
        if not candidate.get("pdf_parts") and not candidate.get("document_link"):
            if local_pdf_source and local_pdf_source.exists():
                local_pdf = _materialize_local_pdf(local_pdf_source, month)
                parse_result = parse_pazomat_invoice(local_pdf) if local_pdf and local_pdf.exists() else PazomatPdfParseResult()
                uploaded = ensure_file_in_folder(drive_folder_id, local_pdf, drive_name=local_pdf.name) if local_pdf and local_pdf.exists() else None
                row.update(
                    {
                        "status": "pdf_available",
                        "source_type": "manual_pdf",
                        "invoice_number": parse_result.invoice_number,
                        "fuel_doc_number": parse_result.fuel_doc_number,
                        "total_amount": parse_result.total_amount,
                        "fuel_amount": parse_result.fuel_amount,
                        "service_amount": parse_result.service_amount,
                        "debit_date": parse_result.debit_date,
                        "vehicle_count": parse_result.vehicle_count,
                        "vehicles_json": parse_result.vehicles_json,
                        "card_count": parse_result.card_count,
                        "cards_json": parse_result.cards_json,
                        "liters_total": parse_result.liters_total,
                        "drive_file_id": str((uploaded or {}).get("id") or ""),
                        "drive_url": str((uploaded or {}).get("web_view_link") or "") or _drive_file_view_link(str((uploaded or {}).get("id") or "")) if uploaded else "",
                        "local_path": str(local_pdf or ""),
                        "notes": "נמצא מייל עבור החודש, והחשבונית הוזנה ידנית מקובץ שסופק והועלתה ל-Drive.",
                        "updated_at": datetime.now().isoformat(timespec="seconds"),
                    }
                )
                rows.append(row)
                continue
            row["status"] = "email_only"
            row["source_type"] = "gmail_email_only"
            row["notes"] = _row_note_for_status("email_only", month)
            rows.append(row)
            continue

        if candidate.get("pdf_parts"):
            local_pdf = _download_month_pdf(service, month, row["gmail_message_id"], candidate.get("pdf_parts") or [])
            source_type = "gmail_pdf_attachment"
            note_key = "pdf_available"
        else:
            local_pdf = _download_month_pdf_from_link(str(candidate.get("document_link") or ""), month)
            source_type = "gmail_pdf_link"
            note_key = "pdf_link_available"
        if not (local_pdf and local_pdf.exists()) and local_pdf_source and local_pdf_source.exists():
            local_pdf = _materialize_local_pdf(local_pdf_source, month)
            source_type = "manual_pdf"
            note_key = "pdf_available"
        if not (local_pdf and local_pdf.exists()):
            row["status"] = "email_only"
            row["source_type"] = source_type
            row["notes"] = f"נמצא קישור למסמכי פזומט עבור {month}, אבל הורדת ה-PDF נכשלה."
            row["updated_at"] = datetime.now().isoformat(timespec="seconds")
            rows.append(row)
            continue
        parse_result = parse_pazomat_invoice(local_pdf) if local_pdf and local_pdf.exists() else PazomatPdfParseResult()
        uploaded = None
        if local_pdf and local_pdf.exists():
            uploaded = ensure_file_in_folder(drive_folder_id, local_pdf, drive_name=local_pdf.name)
        row.update(
            {
                "status": "pdf_available",
                "source_type": source_type,
                "invoice_number": parse_result.invoice_number,
                "fuel_doc_number": parse_result.fuel_doc_number,
                "total_amount": parse_result.total_amount,
                "fuel_amount": parse_result.fuel_amount,
                "service_amount": parse_result.service_amount,
                "debit_date": parse_result.debit_date,
                "vehicle_count": parse_result.vehicle_count,
                "vehicles_json": parse_result.vehicles_json,
                "card_count": parse_result.card_count,
                "cards_json": parse_result.cards_json,
                "liters_total": parse_result.liters_total,
                "drive_file_id": str((uploaded or {}).get("id") or ""),
                "drive_url": str((uploaded or {}).get("web_view_link") or "") or _drive_file_view_link(str((uploaded or {}).get("id") or "")) if uploaded else "",
                "local_path": str(local_pdf or ""),
                "notes": _row_note_for_status(note_key, month),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        rows.append(row)

    save_pazomat_rows(rows)
    return rows


def _json_list(raw: str) -> list[str]:
    try:
        value = json.loads(str(raw or "[]"))
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
    except Exception:
        pass
    return []


def build_pazomat_summary(rows: list[dict]) -> dict:
    expected = [month for month in expected_months() if month.endswith("/2026")]
    rows_by_month = {str(row.get("month") or "").strip(): row for row in rows}
    invoice_months = [month for month in expected if str(rows_by_month.get(month, {}).get("status") or "") == "pdf_available"]
    email_only_months = [month for month in expected if str(rows_by_month.get(month, {}).get("status") or "") == "email_only"]
    missing_email_months = [month for month in expected if month not in rows_by_month or str(rows_by_month.get(month, {}).get("status") or "") == "missing"]
    missing_pdf_months = [month for month in expected if month not in invoice_months]

    unique_cards: set[str] = set()
    unique_vehicles: set[str] = set()
    total_amount = 0.0
    total_fuel_amount = 0.0
    total_service_amount = 0.0
    total_liters = 0.0

    for row in rows:
        if str(row.get("status") or "") != "pdf_available":
            continue
        unique_cards.update(_json_list(row.get("cards_json", "")))
        unique_vehicles.update(_json_list(row.get("vehicles_json", "")))
        for source, target in (
            (row.get("total_amount", ""), "total"),
            (row.get("fuel_amount", ""), "fuel"),
            (row.get("service_amount", ""), "service"),
            (row.get("liters_total", ""), "liters"),
        ):
            try:
                numeric = float(str(source or "").replace(",", ""))
            except Exception:
                numeric = 0.0
            if target == "total":
                total_amount += numeric
            elif target == "fuel":
                total_fuel_amount += numeric
            elif target == "service":
                total_service_amount += numeric
            else:
                total_liters += numeric

    return {
        "expected_months": expected,
        "invoice_months": invoice_months,
        "email_only_months": email_only_months,
        "missing_email_months": missing_email_months,
        "missing_pdf_months": missing_pdf_months,
        "unique_cards": sorted(unique_cards),
        "unique_vehicles": sorted(unique_vehicles),
        "total_amount": _format_money(total_amount),
        "fuel_amount": _format_money(total_fuel_amount),
        "service_amount": _format_money(total_service_amount),
        "liters_total": _format_liters(total_liters),
    }


def build_pazomat_payload(force_refresh: bool = False) -> dict:
    rows = refresh_pazomat_rows() if force_refresh else load_pazomat_rows(force_refresh=False)
    if not rows:
        rows = get_cached_pazomat_rows()
    rows_2026 = _filter_rows_for_year(rows, 2026)
    if not rows:
        try:
            folder_id, folder_url = ensure_pazomat_drive_folder()
        except Exception:
            folder_id, folder_url = "", ""
        return {
            "rows": [],
            "summary": build_pazomat_summary([]),
            "drive_folder_id": folder_id,
            "drive_folder_url": folder_url,
        }
    first_row = rows_2026[0] if rows_2026 else rows[0]
    return {
        "rows": rows_2026,
        "summary": build_pazomat_summary(rows_2026),
        "drive_folder_id": str(first_row.get("drive_folder_id") or ""),
        "drive_folder_url": str(first_row.get("drive_folder_url") or ""),
    }
