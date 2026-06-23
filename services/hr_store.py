import json
import re
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .config import settings
from . import supabase_store
from .google_service_account import build_service_account_credentials
from .runtime_paths import runtime_root

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_SHEET_ID_CACHE: dict[str, int | None] = {}
_SHEET_ENSURED_CACHE: set[str] = set()
_GENERIC_CACHE_TTL_SECONDS = 20

_EMPLOYEE_ROWS_CACHE: list[dict] = []
_EMPLOYEE_ROWS_CACHE_TS = 0.0
_PAYROLL_ROWS_CACHE: list[dict] = []
_PAYROLL_ROWS_CACHE_TS = 0.0
_CONTRIBUTION_ROWS_CACHE: list[dict] = []
_CONTRIBUTION_ROWS_CACHE_TS = 0.0
_HOURS_ROWS_CACHE: list[dict] = []
_HOURS_ROWS_CACHE_TS = 0.0
_DOCUMENT_ROWS_CACHE: list[dict] = []
_DOCUMENT_ROWS_CACHE_TS = 0.0
_PAYSLIP_PREP_HISTORY_ROWS_CACHE: list[dict] = []
_PAYSLIP_PREP_HISTORY_ROWS_CACHE_TS = 0.0

_CACHE_ROOT = runtime_root()
_EMPLOYEE_CACHE_FILE = _CACHE_ROOT / "hr_employees_cache.json"
_PAYROLL_CACHE_FILE = _CACHE_ROOT / "hr_payroll_cache.json"
_CONTRIBUTION_CACHE_FILE = _CACHE_ROOT / "hr_contributions_cache.json"
_HOURS_CACHE_FILE = _CACHE_ROOT / "hr_hours_cache.json"
_DOCUMENT_CACHE_FILE = _CACHE_ROOT / "hr_documents_cache.json"
_PAYSLIP_PREP_HISTORY_CACHE_FILE = _CACHE_ROOT / "hr_payslip_prep_history_cache.json"

_SUPABASE_HR_DOMAINS = {
    "employees": "hr_employees",
    "payroll": "hr_payroll",
    "contributions": "hr_contributions",
    "hours": "hr_hours",
    "documents": "hr_documents",
    "prep_history": "hr_payslip_prep_history",
}


def _supabase_domain(kind: str) -> str | None:
    domain = _SUPABASE_HR_DOMAINS.get(kind)
    if not domain or not supabase_store.is_enabled() or not supabase_store.supports_domain(domain):
        return None
    return domain

EMPLOYEE_HEADERS = [
    "מזהה עובד",
    "שם מלא",
    "תעודת זהות",
    "סוג העסקה",
    "סטטוס",
    "תאריך תחילת עבודה",
    "שכר גלובלי",
    "שכר שעתי",
    "טלפון",
    "אימייל",
    "קרן פנסיה",
    "הערות",
    "מזהה תיקיית דרייב",
    "קישור תיקיית דרייב",
    "עודכן לאחרונה",
]

EMPLOYEE_FIELDS = [
    "employee_id",
    "full_name",
    "id_number",
    "employment_type",
    "active_status",
    "start_date",
    "base_salary",
    "hourly_rate",
    "phone",
    "email",
    "pension_fund",
    "notes",
    "drive_folder_id",
    "drive_folder_url",
    "updated_at",
]

PAYROLL_HEADERS = [
    "מזהה רשומה",
    "מזהה עובד",
    "שם עובד",
    "חודש",
    "סוג העסקה",
    "ברוטו",
    "נטו",
    "שולם",
    "תאריך תשלום",
    "אסמכתא שכר",
    "שם קובץ תלוש",
    "מזהה קובץ תלוש בדרייב",
    "קישור תלוש בדרייב",
    "עודכן לאחרונה",
]

PAYROLL_FIELDS = [
    "row_id",
    "employee_id",
    "employee_name",
    "month_key",
    "employment_type",
    "gross_amount",
    "net_amount",
    "salary_paid",
    "salary_paid_date",
    "salary_reference",
    "payslip_file_name",
    "payslip_drive_file_id",
    "payslip_drive_url",
    "updated_at",
]

CONTRIBUTION_HEADERS = [
    "מזהה רשומה",
    "מזהה עובד",
    "שם עובד",
    "חודש",
    "תגמולי עובד",
    "תגמולי מעסיק",
    "פיצויים",
    "שולם",
    "תאריך תשלום",
    "אסמכתא הפרשה",
    "שם קובץ דוח פיצול",
    "מזהה קובץ דוח פיצול בדרייב",
    "קישור דוח פיצול בדרייב",
    "שם קובץ אסמכתא",
    "מזהה קובץ אסמכתא בדרייב",
    "קישור אסמכתא בדרייב",
    "עודכן לאחרונה",
]

CONTRIBUTION_FIELDS = [
    "row_id",
    "employee_id",
    "employee_name",
    "month_key",
    "employee_contribution",
    "employer_contribution",
    "compensation_amount",
    "paid",
    "paid_date",
    "reference_number",
    "split_report_file_name",
    "split_report_drive_file_id",
    "split_report_drive_url",
    "proof_file_name",
    "proof_drive_file_id",
    "proof_drive_url",
    "updated_at",
]

HOURS_HEADERS = [
    "מזהה רשומה",
    "מזהה עובד",
    "שם עובד",
    "חודש",
    "שעות רגילות",
    "שעות נוספות",
    "שכר לשעה",
    "סטטוס",
    "שם קובץ שעות",
    "מזהה קובץ שעות בדרייב",
    "קישור קובץ שעות בדרייב",
    "עודכן לאחרונה",
]

HOURS_FIELDS = [
    "row_id",
    "employee_id",
    "employee_name",
    "month_key",
    "regular_hours",
    "overtime_hours",
    "hourly_rate",
    "status",
    "hours_file_name",
    "hours_drive_file_id",
    "hours_drive_url",
    "updated_at",
]

DOCUMENT_HEADERS = [
    "מזהה רשומה",
    "מזהה עובד",
    "שם עובד",
    "קטגוריה",
    "כותרת",
    "חודש",
    "שם קובץ",
    "מזהה קובץ בדרייב",
    "קישור קובץ בדרייב",
    "עודכן לאחרונה",
]

DOCUMENT_FIELDS = [
    "row_id",
    "employee_id",
    "employee_name",
    "category",
    "title",
    "month_key",
    "file_name",
    "drive_file_id",
    "drive_url",
    "updated_at",
]

PAYSLIP_PREP_HISTORY_HEADERS = [
    "מזהה רשומה",
    "חודש",
    "תווית חודש",
    "מצב שליחה",
    "נשלח אל",
    "נשלח בתאריך",
    "מספר עובדים",
    "סה\"כ ברוטו לפני נסיעות וניכוי",
    "מספר צרופות",
    "JSON סיכומי מסמכים תומכים",
    "הערות",
    "עודכן לאחרונה",
]

PAYSLIP_PREP_HISTORY_FIELDS = [
    "row_id",
    "month_key",
    "month_label",
    "send_mode",
    "sent_to",
    "sent_at",
    "employees_total",
    "gross_total_label",
    "attachments_count",
    "supporting_summaries_json",
    "notes",
    "updated_at",
]

DEFAULT_EMPLOYEE_ROWS = [
    {
        "employee_id": "emp_david_ben_yacov",
        "full_name": "בן יעקב דוד",
        "id_number": "52341641",
        "employment_type": "global",
        "active_status": "active",
        "start_date": "",
        "base_salary": "5900.00",
        "hourly_rate": "",
        "phone": "0505204010",
        "email": "",
        "pension_fund": "",
        "notes": "",
        "drive_folder_id": "",
        "drive_folder_url": "",
        "updated_at": "",
    },
    {
        "employee_id": "emp_malka_ben_yacov",
        "full_name": "בן יעקב מלכה",
        "id_number": "54486873",
        "employment_type": "global",
        "active_status": "active",
        "start_date": "",
        "base_salary": "3500.00",
        "hourly_rate": "",
        "phone": "0503011503",
        "email": "",
        "pension_fund": "",
        "notes": "",
        "drive_folder_id": "",
        "drive_folder_url": "",
        "updated_at": "",
    },
    {
        "employee_id": "emp_tawuchao_damlau",
        "full_name": "דמלאו טווצ'או",
        "id_number": "332594274",
        "employment_type": "global",
        "active_status": "active",
        "start_date": "",
        "base_salary": "6000.00",
        "hourly_rate": "",
        "phone": "",
        "email": "",
        "pension_fund": "מיטב פנסיה מקיפה",
        "notes": "",
        "drive_folder_id": "",
        "drive_folder_url": "",
        "updated_at": "",
    },
    {
        "employee_id": "emp_solomon_shibshi",
        "full_name": "שיבשי סלומון",
        "id_number": "206739153",
        "employment_type": "hourly",
        "active_status": "active",
        "start_date": "2024-12-01",
        "base_salary": "",
        "hourly_rate": "50.00",
        "phone": "",
        "email": "",
        "pension_fund": "מיטב פנסיה מקיפה",
        "notes": "עובד שעתי, 50 ש\"ח לשעה.",
        "drive_folder_id": "",
        "drive_folder_url": "",
        "updated_at": "",
    },
]


def _service():
    creds = build_service_account_credentials(SCOPES)
    return build("sheets", "v4", credentials=creds)


def _sheet_id_by_title(service, title: str):
    metadata = service.spreadsheets().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {}) or {}
        if str(props.get("title") or "").strip() == title:
            sheet_id = props.get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id
            return sheet_id
    return None


def _sheet_cache_file(kind: str) -> Path:
    return {
        "employees": _EMPLOYEE_CACHE_FILE,
        "payroll": _PAYROLL_CACHE_FILE,
        "contributions": _CONTRIBUTION_CACHE_FILE,
        "hours": _HOURS_CACHE_FILE,
        "documents": _DOCUMENT_CACHE_FILE,
        "prep_history": _PAYSLIP_PREP_HISTORY_CACHE_FILE,
    }[kind]


def _sheet_tab_name(kind: str) -> str:
    return {
        "employees": settings.google_sheets_hr_employees_tab,
        "payroll": settings.google_sheets_hr_payroll_tab,
        "contributions": settings.google_sheets_hr_contributions_tab,
        "hours": settings.google_sheets_hr_hours_tab,
        "documents": settings.google_sheets_hr_documents_tab,
        "prep_history": settings.google_sheets_hr_payslip_prep_history_tab,
    }[kind]


def _sheet_headers(kind: str) -> list[str]:
    return {
        "employees": EMPLOYEE_HEADERS,
        "payroll": PAYROLL_HEADERS,
        "contributions": CONTRIBUTION_HEADERS,
        "hours": HOURS_HEADERS,
        "documents": DOCUMENT_HEADERS,
        "prep_history": PAYSLIP_PREP_HISTORY_HEADERS,
    }[kind]


def _sheet_fields(kind: str) -> list[str]:
    return {
        "employees": EMPLOYEE_FIELDS,
        "payroll": PAYROLL_FIELDS,
        "contributions": CONTRIBUTION_FIELDS,
        "hours": HOURS_FIELDS,
        "documents": DOCUMENT_FIELDS,
        "prep_history": PAYSLIP_PREP_HISTORY_FIELDS,
    }[kind]


def _set_cache(kind: str, rows: list[dict]) -> None:
    global _EMPLOYEE_ROWS_CACHE, _EMPLOYEE_ROWS_CACHE_TS
    global _PAYROLL_ROWS_CACHE, _PAYROLL_ROWS_CACHE_TS
    global _CONTRIBUTION_ROWS_CACHE, _CONTRIBUTION_ROWS_CACHE_TS
    global _HOURS_ROWS_CACHE, _HOURS_ROWS_CACHE_TS
    global _DOCUMENT_ROWS_CACHE, _DOCUMENT_ROWS_CACHE_TS
    global _PAYSLIP_PREP_HISTORY_ROWS_CACHE, _PAYSLIP_PREP_HISTORY_ROWS_CACHE_TS
    normalized = [dict(row) for row in rows]
    now = time.time()
    if kind == "employees":
        _EMPLOYEE_ROWS_CACHE = normalized
        _EMPLOYEE_ROWS_CACHE_TS = now
    elif kind == "payroll":
        _PAYROLL_ROWS_CACHE = normalized
        _PAYROLL_ROWS_CACHE_TS = now
    elif kind == "contributions":
        _CONTRIBUTION_ROWS_CACHE = normalized
        _CONTRIBUTION_ROWS_CACHE_TS = now
    elif kind == "hours":
        _HOURS_ROWS_CACHE = normalized
        _HOURS_ROWS_CACHE_TS = now
    elif kind == "prep_history":
        _PAYSLIP_PREP_HISTORY_ROWS_CACHE = normalized
        _PAYSLIP_PREP_HISTORY_ROWS_CACHE_TS = now
    else:
        _DOCUMENT_ROWS_CACHE = normalized
        _DOCUMENT_ROWS_CACHE_TS = now


def _get_cache(kind: str) -> tuple[list[dict], float]:
    if kind == "employees":
        return _EMPLOYEE_ROWS_CACHE, _EMPLOYEE_ROWS_CACHE_TS
    if kind == "payroll":
        return _PAYROLL_ROWS_CACHE, _PAYROLL_ROWS_CACHE_TS
    if kind == "contributions":
        return _CONTRIBUTION_ROWS_CACHE, _CONTRIBUTION_ROWS_CACHE_TS
    if kind == "hours":
        return _HOURS_ROWS_CACHE, _HOURS_ROWS_CACHE_TS
    if kind == "prep_history":
        return _PAYSLIP_PREP_HISTORY_ROWS_CACHE, _PAYSLIP_PREP_HISTORY_ROWS_CACHE_TS
    return _DOCUMENT_ROWS_CACHE, _DOCUMENT_ROWS_CACHE_TS


def _normalize_bool(value) -> str:
    return "TRUE" if str(value or "").strip().lower() in {"1", "true", "yes", "כן"} else ""


def _normalize_amount(value) -> str:
    raw = str(value or "").strip().replace(",", "")
    if not raw:
        return ""
    try:
        return f"{float(raw):.2f}"
    except Exception:
        return raw


def _normalize_month_key(value) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if re.match(r"^\d{4}-\d{2}$", raw):
        return raw
    match = re.search(r"(\d{4})[-/](\d{1,2})", raw)
    if match:
        year, month = match.groups()
        return f"{year}-{int(month):02d}"
    return raw


def _normalize_employee_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in EMPLOYEE_FIELDS}
    normalized["employee_id"] = str(normalized.get("employee_id") or uuid4()).strip()
    normalized["full_name"] = re.sub(r"\s+", " ", str(normalized.get("full_name") or "").strip())
    normalized["id_number"] = re.sub(r"\D+", "", str(normalized.get("id_number") or ""))
    normalized["employment_type"] = "hourly" if str(normalized.get("employment_type") or "").strip().lower() == "hourly" else "global"
    normalized["active_status"] = "inactive" if str(normalized.get("active_status") or "").strip().lower() == "inactive" else "active"
    normalized["base_salary"] = _normalize_amount(normalized.get("base_salary"))
    normalized["hourly_rate"] = _normalize_amount(normalized.get("hourly_rate"))
    normalized["phone"] = str(normalized.get("phone") or "").strip()
    normalized["email"] = str(normalized.get("email") or "").strip()
    normalized["pension_fund"] = re.sub(r"\s+", " ", str(normalized.get("pension_fund") or "").strip())
    normalized["notes"] = str(normalized.get("notes") or "").strip()
    normalized["drive_folder_id"] = str(normalized.get("drive_folder_id") or "").strip()
    normalized["drive_folder_url"] = str(normalized.get("drive_folder_url") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_payroll_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in PAYROLL_FIELDS}
    normalized["row_id"] = str(normalized.get("row_id") or uuid4()).strip()
    normalized["employee_id"] = str(normalized.get("employee_id") or "").strip()
    normalized["employee_name"] = re.sub(r"\s+", " ", str(normalized.get("employee_name") or "").strip())
    normalized["month_key"] = _normalize_month_key(normalized.get("month_key"))
    normalized["employment_type"] = "hourly" if str(normalized.get("employment_type") or "").strip().lower() == "hourly" else "global"
    normalized["gross_amount"] = _normalize_amount(normalized.get("gross_amount"))
    normalized["net_amount"] = _normalize_amount(normalized.get("net_amount"))
    normalized["salary_paid"] = _normalize_bool(normalized.get("salary_paid"))
    normalized["salary_paid_date"] = str(normalized.get("salary_paid_date") or "").strip()
    normalized["salary_reference"] = str(normalized.get("salary_reference") or "").strip()
    normalized["payslip_file_name"] = str(normalized.get("payslip_file_name") or "").strip()
    normalized["payslip_drive_file_id"] = str(normalized.get("payslip_drive_file_id") or "").strip()
    normalized["payslip_drive_url"] = str(normalized.get("payslip_drive_url") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_contribution_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in CONTRIBUTION_FIELDS}
    normalized["row_id"] = str(normalized.get("row_id") or uuid4()).strip()
    normalized["employee_id"] = str(normalized.get("employee_id") or "").strip()
    normalized["employee_name"] = re.sub(r"\s+", " ", str(normalized.get("employee_name") or "").strip())
    normalized["month_key"] = _normalize_month_key(normalized.get("month_key"))
    normalized["employee_contribution"] = _normalize_amount(normalized.get("employee_contribution"))
    normalized["employer_contribution"] = _normalize_amount(normalized.get("employer_contribution"))
    normalized["compensation_amount"] = _normalize_amount(normalized.get("compensation_amount"))
    normalized["paid"] = _normalize_bool(normalized.get("paid"))
    normalized["paid_date"] = str(normalized.get("paid_date") or "").strip()
    normalized["reference_number"] = str(normalized.get("reference_number") or "").strip()
    normalized["split_report_file_name"] = str(normalized.get("split_report_file_name") or "").strip()
    normalized["split_report_drive_file_id"] = str(normalized.get("split_report_drive_file_id") or "").strip()
    normalized["split_report_drive_url"] = str(normalized.get("split_report_drive_url") or "").strip()
    normalized["proof_file_name"] = str(normalized.get("proof_file_name") or "").strip()
    normalized["proof_drive_file_id"] = str(normalized.get("proof_drive_file_id") or "").strip()
    normalized["proof_drive_url"] = str(normalized.get("proof_drive_url") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_hours_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in HOURS_FIELDS}
    normalized["row_id"] = str(normalized.get("row_id") or uuid4()).strip()
    normalized["employee_id"] = str(normalized.get("employee_id") or "").strip()
    normalized["employee_name"] = re.sub(r"\s+", " ", str(normalized.get("employee_name") or "").strip())
    normalized["month_key"] = _normalize_month_key(normalized.get("month_key"))
    normalized["regular_hours"] = _normalize_amount(normalized.get("regular_hours"))
    normalized["overtime_hours"] = _normalize_amount(normalized.get("overtime_hours"))
    normalized["hourly_rate"] = _normalize_amount(normalized.get("hourly_rate"))
    normalized["status"] = str(normalized.get("status") or "").strip() or "open"
    normalized["hours_file_name"] = str(normalized.get("hours_file_name") or "").strip()
    normalized["hours_drive_file_id"] = str(normalized.get("hours_drive_file_id") or "").strip()
    normalized["hours_drive_url"] = str(normalized.get("hours_drive_url") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_document_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in DOCUMENT_FIELDS}
    normalized["row_id"] = str(normalized.get("row_id") or uuid4()).strip()
    normalized["employee_id"] = str(normalized.get("employee_id") or "").strip()
    normalized["employee_name"] = re.sub(r"\s+", " ", str(normalized.get("employee_name") or "").strip())
    normalized["category"] = str(normalized.get("category") or "").strip() or "general"
    normalized["title"] = re.sub(r"\s+", " ", str(normalized.get("title") or "").strip())
    normalized["month_key"] = _normalize_month_key(normalized.get("month_key"))
    normalized["file_name"] = str(normalized.get("file_name") or "").strip()
    normalized["drive_file_id"] = str(normalized.get("drive_file_id") or "").strip()
    normalized["drive_url"] = str(normalized.get("drive_url") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_payslip_prep_history_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in PAYSLIP_PREP_HISTORY_FIELDS}
    normalized["row_id"] = str(normalized.get("row_id") or uuid4()).strip()
    normalized["month_key"] = _normalize_month_key(normalized.get("month_key"))
    normalized["month_label"] = re.sub(r"\s+", " ", str(normalized.get("month_label") or "").strip())
    normalized["send_mode"] = "test" if str(normalized.get("send_mode") or "").strip().lower() == "test" else "live"
    normalized["sent_to"] = str(normalized.get("sent_to") or "").strip()
    normalized["sent_at"] = str(normalized.get("sent_at") or "").strip()
    normalized["employees_total"] = str(int(float(str(normalized.get("employees_total") or "0").strip() or 0))) if str(normalized.get("employees_total") or "").strip() else "0"
    normalized["gross_total_label"] = str(normalized.get("gross_total_label") or "").strip()
    normalized["attachments_count"] = str(int(float(str(normalized.get("attachments_count") or "0").strip() or 0))) if str(normalized.get("attachments_count") or "").strip() else "0"
    normalized["supporting_summaries_json"] = str(normalized.get("supporting_summaries_json") or "[]").strip() or "[]"
    normalized["notes"] = str(normalized.get("notes") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalizer(kind: str):
    return {
        "employees": _normalize_employee_row,
        "payroll": _normalize_payroll_row,
        "contributions": _normalize_contribution_row,
        "hours": _normalize_hours_row,
        "documents": _normalize_document_row,
        "prep_history": _normalize_payslip_prep_history_row,
    }[kind]


def _sort_rows(kind: str, rows: list[dict]) -> list[dict]:
    if kind == "employees":
        return sorted(rows, key=lambda row: (str(row.get("active_status") or "") != "active", str(row.get("full_name") or "")))
    if kind == "documents":
        return sorted(rows, key=lambda row: (str(row.get("employee_name") or ""), str(row.get("month_key") or ""), str(row.get("title") or "")))
    if kind == "prep_history":
        return sorted(rows, key=lambda row: (str(row.get("sent_at") or ""), str(row.get("month_key") or "")), reverse=True)
    return sorted(rows, key=lambda row: (str(row.get("month_key") or ""), str(row.get("employee_name") or "")), reverse=True)


def _load_disk_cache(kind: str) -> list[dict]:
    try:
        cache_file = _sheet_cache_file(kind)
        if not cache_file.exists():
            return []
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        normalizer = _normalizer(kind)
        return [normalizer(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _save_disk_cache(kind: str, rows: list[dict]) -> None:
    try:
        _sheet_cache_file(kind).write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": rows,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _ensure_sheet(service, kind: str):
    title = _sheet_tab_name(kind)
    headers = _sheet_headers(kind)
    if title in _SHEET_ENSURED_CACHE:
        return title, _SHEET_ID_CACHE.get(title)
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        try:
            response = service.spreadsheets().batchUpdate(
                spreadsheetId=settings.google_sheets_spreadsheet_id,
                body=body,
            ).execute()
            replies = response.get("replies", [])
            if replies:
                sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
                _SHEET_ID_CACHE[title] = sheet_id
        except HttpError as exc:
            message = str(exc)
            if "already exists" not in message:
                raise
            sheet_id = _sheet_id_by_title(service, title)
    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    if first_row != headers:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()
    _SHEET_ENSURED_CACHE.add(title)
    return title, sheet_id


def get_cached_rows(kind: str) -> list[dict]:
    cache_rows, _ = _get_cache(kind)
    if cache_rows:
        return [dict(row) for row in cache_rows]
    disk_rows = _load_disk_cache(kind)
    if disk_rows:
        _set_cache(kind, disk_rows)
        return [dict(row) for row in disk_rows]
    if kind == "employees":
        seeded = [_normalize_employee_row(row) for row in DEFAULT_EMPLOYEE_ROWS]
        _set_cache(kind, seeded)
        _save_disk_cache(kind, seeded)
        return [dict(row) for row in seeded]
    return []


def load_rows(kind: str, force_refresh: bool = False) -> list[dict]:
    cache_rows, cache_ts = _get_cache(kind)
    if not force_refresh and cache_rows and (time.time() - cache_ts) <= _GENERIC_CACHE_TTL_SECONDS:
        return [dict(row) for row in cache_rows]
    supabase_domain = _supabase_domain(kind)
    if supabase_domain:
        try:
            normalizer = _normalizer(kind)
            rows = [normalizer(row) for row in supabase_store.fetch_domain_rows(supabase_domain)]
            if kind == "employees" and not rows:
                rows = [_normalize_employee_row(row) for row in DEFAULT_EMPLOYEE_ROWS]
                save_rows("employees", rows)
                return rows
            rows = _sort_rows(kind, rows)
            _set_cache(kind, rows)
            _save_disk_cache(kind, rows)
            return rows
        except Exception:
            if cache_rows:
                return [dict(row) for row in cache_rows]
            disk_rows = _load_disk_cache(kind)
            if disk_rows:
                _set_cache(kind, disk_rows)
                return [dict(row) for row in disk_rows]
            raise
    service = _service()
    title, _ = _ensure_sheet(service, kind)
    fields = _sheet_fields(kind)
    end_col = chr(64 + min(len(fields), 26))
    result = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A2:{end_col}",
    ).execute()
    values = result.get("values", [])
    rows: list[dict] = []
    normalizer = _normalizer(kind)
    for raw in values:
        padded = raw + [""] * max(0, len(fields) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(fields)}
        if any(str(value).strip() for value in row.values()):
            rows.append(normalizer(row))
    if kind == "employees" and not rows:
        rows = [_normalize_employee_row(row) for row in DEFAULT_EMPLOYEE_ROWS]
        save_rows("employees", rows)
        return rows
    rows = _sort_rows(kind, rows)
    _set_cache(kind, rows)
    _save_disk_cache(kind, rows)
    return rows


def save_rows(kind: str, rows: list[dict]) -> dict:
    normalizer = _normalizer(kind)
    normalized_rows = _sort_rows(kind, [normalizer(row) for row in (rows or [])])
    current_rows, _ = _get_cache(kind)
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(current_rows, ensure_ascii=False, sort_keys=True):
        return {"sheet": f"supabase:{kind}" if _supabase_domain(kind) else kind, "rows_saved": len(normalized_rows), "skipped": True}
    supabase_domain = _supabase_domain(kind)
    if supabase_domain:
        result = supabase_store.replace_domain_rows(supabase_domain, normalized_rows)
        _set_cache(kind, normalized_rows)
        _save_disk_cache(kind, normalized_rows)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_sheet(service, kind)
    fields = _sheet_fields(kind)
    headers = _sheet_headers(kind)
    end_col = chr(64 + min(len(fields), 26))
    values = [headers] + [[row.get(field, "") for field in fields] for row in normalized_rows]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A:{end_col}",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _set_cache(kind, normalized_rows)
    _save_disk_cache(kind, normalized_rows)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def upsert_row(kind: str, row: dict, key_field: str) -> dict:
    rows = load_rows(kind)
    normalizer = _normalizer(kind)
    normalized = normalizer(row)
    key_value = str(normalized.get(key_field) or "").strip()
    if not key_value:
        key_value = str(uuid4())
        normalized[key_field] = key_value
    updated = False
    next_rows: list[dict] = []
    for existing in rows:
        if str(existing.get(key_field) or "").strip() == key_value:
            next_rows.append(normalized)
            updated = True
        else:
            next_rows.append(existing)
    if not updated:
        next_rows.append(normalized)
    save_result = save_rows(kind, next_rows)
    return {"status": "ok", "row": normalized, "save_result": save_result, "rows": next_rows}


def load_hr_state(force_refresh: bool = False) -> dict:
    employees = load_rows("employees", force_refresh=force_refresh)
    payroll = load_rows("payroll", force_refresh=force_refresh)
    contributions = load_rows("contributions", force_refresh=force_refresh)
    hours = load_rows("hours", force_refresh=force_refresh)
    documents = load_rows("documents", force_refresh=force_refresh)
    prep_history = load_rows("prep_history", force_refresh=force_refresh)
    active_employees = [row for row in employees if str(row.get("active_status") or "") == "active"]
    hourly_employees = [row for row in active_employees if str(row.get("employment_type") or "") == "hourly"]
    global_employees = [row for row in active_employees if str(row.get("employment_type") or "") == "global"]
    return {
        "employees": employees,
        "payroll_rows": payroll,
        "contribution_rows": contributions,
        "hours_rows": hours,
        "document_rows": documents,
        "prep_history_rows": prep_history,
        "summary": {
            "employees_total": len(active_employees),
            "employees_global": len(global_employees),
            "employees_hourly": len(hourly_employees),
            "payroll_rows": len(payroll),
            "contribution_rows": len(contributions),
            "hours_rows": len(hours),
            "document_rows": len(documents),
            "prep_history_rows": len(prep_history),
        },
    }
