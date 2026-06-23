from __future__ import annotations

import base64
import re
import subprocess
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

from .gmail_oauth import _gmail_service
from .google_drive_sync import ensure_child_folder, ensure_file_in_folder, managed_storage_root_folder_id
from .google_sheets import get_cached_sibus_rows, load_sibus_rows, save_sibus_rows
from .runtime_paths import runtime_root


SIBUS_OUTPUT_DIR = runtime_root() / "output" / "sibus_sync"
SIBUS_DRIVE_ROOT_TITLE = "מסמכי מנהלה"
SIBUS_DRIVE_FOLDER_TITLE = "סיבוס"
SIBUS_QUERY = "from:noreply@invoices.pluxee.co.il after:2026/02/02"
SIBUS_EXPECTED_START = date(2026, 1, 1)
_BIDI_CHARS = "\u202a\u202b\u202c\u202d\u202e\u200f\u200e\ufeff"
_ATTACHMENT_NAME_SAFE = re.compile(r"[^A-Za-z0-9._() \-\u0590-\u05FF]+")


def _month_key(dt: date) -> str:
    return dt.strftime("%m/%Y")


def _previous_month(value: date) -> date:
    return (value.replace(day=1) - timedelta(days=1)).replace(day=1)


def expected_months(today: date | None = None) -> list[str]:
    today = today or date.today()
    last_expected = _previous_month(today)
    current = SIBUS_EXPECTED_START
    months: list[str] = []
    while current <= last_expected:
        months.append(_month_key(current))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months


def _month_sort_value(label: str) -> tuple[int, int]:
    raw = str(label or "").strip()
    try:
        month_text, year_text = raw.split("/", 1)
        return int(year_text), int(month_text)
    except Exception:
        return (9999, 99)


def _drive_folder_view_link(folder_id: str) -> str:
    return f"https://drive.google.com/drive/folders/{folder_id}"


def _drive_file_view_link(file_id: str) -> str:
    return f"https://drive.google.com/file/d/{file_id}/view?usp=drivesdk"


def ensure_sibus_drive_folder() -> tuple[str, str]:
    parent_id = ensure_child_folder(managed_storage_root_folder_id(), SIBUS_DRIVE_ROOT_TITLE)
    folder_id = ensure_child_folder(parent_id, SIBUS_DRIVE_FOLDER_TITLE)
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


def _decode_gmail_attachment_data(data: str) -> bytes:
    raw = str(data or "").strip()
    padded = raw + "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _safe_attachment_name(name: str, month: str) -> str:
    base_name = _ATTACHMENT_NAME_SAFE.sub("_", str(name or "").strip()).strip("._ ") or "invoice.pdf"
    return f"{month.replace('/', '-') }__{base_name}".replace(" ", "_")


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
    match = re.search(r"([\d,]+\.\d{2})", str(line or ""))
    return match.group(1).replace(",", "") if match else ""


def _parse_leading_amount(line: str) -> str:
    match = re.match(r"\s*([\d,]+\.\d{2})", str(line or ""))
    return match.group(1).replace(",", "") if match else ""


def _format_money(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.2f}"


def _message_received_month(headers: dict[str, str], internal_date: int) -> str:
    parsed = None
    try:
        parsed = parsedate_to_datetime(headers.get("date", ""))
    except Exception:
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromtimestamp(internal_date / 1000)
        except Exception:
            parsed = datetime.now()
    if hasattr(parsed, "date"):
        parsed_date = parsed.date()
    else:
        parsed_date = date.today()
    return _month_key(_previous_month(parsed_date))


@dataclass
class SibusPdfParseResult:
    invoice_number: str = ""
    invoice_date: str = ""
    billing_period: str = ""
    due_date: str = ""
    subtotal_amount: str = ""
    vat_amount: str = ""
    total_amount: str = ""
    customer_number: str = ""


def parse_sibus_invoice(pdf_path: Path) -> SibusPdfParseResult:
    lines = _run_pdftotext(pdf_path)
    invoice_number = ""
    invoice_date = ""
    billing_period = ""
    due_date = ""
    subtotal_amount = ""
    vat_amount = ""
    total_amount = ""
    customer_number = ""

    for line in lines:
        if not invoice_date and "תאריך חשבונית" in line:
            match = re.search(r"תאריך חשבונית[: ]+(\d{2}/\d{2}/\d{2})", line)
            if match:
                invoice_date = match.group(1)
        if not invoice_number and "חשבונית" in line:
            match = re.search(r"([A-Z]{2}\d{6,})", line)
            if match:
                invoice_number = match.group(1)
        if not billing_period and "פרטים" in line:
            match = re.search(r"(\d{2}/\d{2}/\d{2})-(\d{2}/\d{2}/\d{2})", line)
            if match:
                billing_period = f"{match.group(1)} - {match.group(2)}"
        if not due_date and "לתשלום עד" in line:
            match = re.search(r"לתשלום עד[: ]+(\d{2}/\d{2}/\d{2})", line)
            if match:
                due_date = match.group(1)
        if not customer_number and "מס" in line and "לקוח" in line:
            match = re.search(r"(CCC\d+)", line) or re.search(r"מס[\\. ]*לקוח[: ]+([A-Z0-9]+)", line)
            if match:
                customer_number = match.group(1)
        if not subtotal_amount and "סכום חייב במע" in line:
            subtotal_amount = _parse_leading_amount(line) or _parse_amount_from_line(line)
        if not vat_amount and "מע\"מ" in line and "סכום חייב" not in line:
            vat_amount = _parse_leading_amount(line) or _parse_amount_from_line(line)
        if not total_amount and "סה\"כ מחיר" in line:
            total_amount = _parse_leading_amount(line) or _parse_amount_from_line(line)

    return SibusPdfParseResult(
        invoice_number=invoice_number,
        invoice_date=invoice_date,
        billing_period=billing_period,
        due_date=due_date,
        subtotal_amount=subtotal_amount,
        vat_amount=vat_amount,
        total_amount=total_amount,
        customer_number=customer_number,
    )


def _gmail_message_candidates() -> dict[str, dict]:
    service = _gmail_service()
    response = service.users().messages().list(userId="me", q=SIBUS_QUERY, maxResults=100).execute()
    messages = response.get("messages") or []
    candidates: dict[str, dict] = {}
    expected = set(expected_months())

    for item in messages:
        message_id = str(item.get("id") or "").strip()
        if not message_id:
            continue
        message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        payload = message.get("payload") or {}
        headers = _message_headers(payload)
        internal_date = int(str(message.get("internalDate") or "0") or 0)
        month = _message_received_month(headers, internal_date)
        if month not in expected:
            continue
        pdf_parts = []
        for part in _walk_parts(payload.get("parts") or []):
            filename = str(part.get("filename") or "").strip()
            attachment_id = str((part.get("body") or {}).get("attachmentId") or "").strip()
            if filename.lower().endswith(".pdf") and attachment_id:
                pdf_parts.append({"filename": filename, "attachment_id": attachment_id})
        candidate = {
            "month": month,
            "message_id": message_id,
            "subject": headers.get("subject", ""),
            "internal_date": internal_date,
            "pdf_parts": pdf_parts,
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
        if current_has_pdf == existing_has_pdf and internal_date > int(existing.get("internal_date") or 0):
            candidates[month] = candidate
    return candidates


def _download_month_pdf(service, month: str, message_id: str, pdf_parts: list[dict]) -> Path | None:
    if not pdf_parts:
        return None
    SIBUS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    part = pdf_parts[0]
    attachment = service.users().messages().attachments().get(
        userId="me",
        messageId=message_id,
        id=str(part.get("attachment_id") or ""),
    ).execute()
    raw = _decode_gmail_attachment_data(attachment.get("data", ""))
    target = SIBUS_OUTPUT_DIR / _safe_attachment_name(str(part.get("filename") or "invoice.pdf"), month)
    target.write_bytes(raw)
    return target


def _row_note_for_status(status: str, month: str) -> str:
    if status == "pdf_available":
        return "נמצאה חשבונית PDF של סיבוס והועלתה ל-Drive."
    if status == "email_only":
        return f"נמצא מייל עבור {month}, אבל לא נמצאה חשבונית PDF usable כצרופה."
    return f"לא נמצא כרגע מייל חשבונית של סיבוס עבור {month}."


def refresh_sibus_rows() -> list[dict]:
    expected = expected_months()
    service = _gmail_service()
    candidates = _gmail_message_candidates()
    drive_folder_id, drive_folder_url = ensure_sibus_drive_folder()
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
            "invoice_date": "",
            "billing_period": "",
            "due_date": "",
            "subtotal_amount": "",
            "vat_amount": "",
            "total_amount": "",
            "customer_number": "",
            "drive_folder_id": drive_folder_id,
            "drive_folder_url": drive_folder_url,
            "drive_file_id": "",
            "drive_url": "",
            "local_path": "",
            "notes": _row_note_for_status("missing", month),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        if not candidate:
            rows.append(row)
            continue

        row["gmail_message_id"] = str(candidate.get("message_id") or "")
        row["subject"] = str(candidate.get("subject") or "")
        if not candidate.get("pdf_parts"):
            row["status"] = "email_only"
            row["source_type"] = "gmail_email_only"
            row["notes"] = _row_note_for_status("email_only", month)
            rows.append(row)
            continue

        local_pdf = _download_month_pdf(service, month, row["gmail_message_id"], candidate.get("pdf_parts") or [])
        parse_result = parse_sibus_invoice(local_pdf) if local_pdf and local_pdf.exists() else SibusPdfParseResult()
        uploaded = None
        if local_pdf and local_pdf.exists():
            uploaded = ensure_file_in_folder(drive_folder_id, local_pdf, drive_name=local_pdf.name)
        row.update(
            {
                "status": "pdf_available",
                "source_type": "gmail_pdf_attachment",
                "invoice_number": parse_result.invoice_number,
                "invoice_date": parse_result.invoice_date,
                "billing_period": parse_result.billing_period,
                "due_date": parse_result.due_date,
                "subtotal_amount": parse_result.subtotal_amount,
                "vat_amount": parse_result.vat_amount,
                "total_amount": parse_result.total_amount,
                "customer_number": parse_result.customer_number,
                "drive_file_id": str((uploaded or {}).get("id") or ""),
                "drive_url": (
                    str((uploaded or {}).get("web_view_link") or "")
                    or _drive_file_view_link(str((uploaded or {}).get("id") or ""))
                    if uploaded else ""
                ),
                "local_path": str(local_pdf or ""),
                "notes": _row_note_for_status("pdf_available", month),
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        rows.append(row)

    save_sibus_rows(rows)
    return rows


def build_sibus_summary(rows: list[dict]) -> dict:
    expected = expected_months()
    rows_by_month = {str(row.get("month") or "").strip(): row for row in rows}
    invoice_months = [month for month in expected if str(rows_by_month.get(month, {}).get("status") or "") == "pdf_available"]
    email_only_months = [month for month in expected if str(rows_by_month.get(month, {}).get("status") or "") == "email_only"]
    missing_email_months = [month for month in expected if month not in rows_by_month or str(rows_by_month.get(month, {}).get("status") or "") == "missing"]
    missing_pdf_months = [month for month in expected if month not in invoice_months]

    total_amount = 0.0
    subtotal_amount = 0.0
    vat_amount = 0.0
    for row in rows:
        if str(row.get("status") or "") != "pdf_available":
            continue
        for source, target in (
            (row.get("total_amount", ""), "total"),
            (row.get("subtotal_amount", ""), "subtotal"),
            (row.get("vat_amount", ""), "vat"),
        ):
            try:
                numeric = float(str(source or "").replace(",", ""))
            except Exception:
                numeric = 0.0
            if target == "total":
                total_amount += numeric
            elif target == "subtotal":
                subtotal_amount += numeric
            else:
                vat_amount += numeric

    return {
        "expected_months": expected,
        "invoice_months": invoice_months,
        "email_only_months": email_only_months,
        "missing_email_months": missing_email_months,
        "missing_pdf_months": missing_pdf_months,
        "total_amount": _format_money(total_amount),
        "subtotal_amount": _format_money(subtotal_amount),
        "vat_amount": _format_money(vat_amount),
    }


def build_sibus_payload(force_refresh: bool = False) -> dict:
    rows = refresh_sibus_rows() if force_refresh else load_sibus_rows(force_refresh=False)
    if not rows:
        rows = get_cached_sibus_rows()
    if not rows:
        try:
            folder_id, folder_url = ensure_sibus_drive_folder()
        except Exception:
            folder_id, folder_url = "", ""
        return {
            "rows": [],
            "summary": build_sibus_summary([]),
            "drive_folder_id": folder_id,
            "drive_folder_url": folder_url,
        }
    first_row = rows[0]
    return {
        "rows": sorted(rows, key=lambda row: _month_sort_value(str(row.get("month") or ""))),
        "summary": build_sibus_summary(rows),
        "drive_folder_id": str(first_row.get("drive_folder_id") or ""),
        "drive_folder_url": str(first_row.get("drive_folder_url") or ""),
    }
