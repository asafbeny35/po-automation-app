from dotenv import load_dotenv
load_dotenv()

import os
from pathlib import Path
from pydantic_settings import BaseSettings

DEFAULT_SUPABASE_URL = "https://vfmrsljkdwgshclqrmiw.supabase.co"
DEFAULT_SUPABASE_ANON_KEY = "sb_publishable_ILAaqVDWG_N4c73GyTcCfQ_TyPWiCC5"
DEFAULT_SUPABASE_SERVICE_ROLE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InZmbXJzbGprZHdnc2hjbHFybWl3Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MTc4NjI5OCwiZXhwIjoyMDk3MzYyMjk4fQ.AHxPTZw1mIMD6qnElL0szt5yQMrzbUfF2hz0TFzglZI"
DEFAULT_PUBLIC_BASE_URL = "https://poautomationapp.vercel.app"


def _fallback_env_value(key: str, default: str = "") -> str:
    for filename in (".env", ".env.save"):
        path = Path(__file__).resolve().parents[1] / filename
        if not path.exists():
            continue
        try:
            for raw_line in path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                current_key, current_value = line.split("=", 1)
                if current_key.strip() == key:
                    return current_value.strip()
        except Exception:
            continue
    return default


def _env_or_fallback(key: str, default: str = "") -> str:
    value = os.getenv(key, "").strip()
    if value and value != "XXXXXXXXXXXXXXX":
        return value
    fallback = _fallback_env_value(key, default).strip()
    if fallback and fallback != "XXXXXXXXXXXXXXX":
        return fallback
    return default


class Settings(BaseSettings):
    app_public_base_url: str = _env_or_fallback("APP_PUBLIC_BASE_URL", DEFAULT_PUBLIC_BASE_URL)
    data_backend: str = _env_or_fallback("DATA_BACKEND", "google_sheets")
    backend_api_base_url: str = _env_or_fallback("BACKEND_API_BASE_URL", DEFAULT_PUBLIC_BASE_URL)
    greeninvoice_sandbox_api_key: str = os.getenv("GREENINVOICE_SANDBOX_API_KEY", "")
    greeninvoice_sandbox_api_secret: str = os.getenv("GREENINVOICE_SANDBOX_API_SECRET", "")
    greeninvoice_sandbox_base_url: str = os.getenv("GREENINVOICE_SANDBOX_BASE_URL", "https://sandbox.d.greeninvoice.co.il/api/v1")

    greeninvoice_prod_api_key: str = os.getenv("GREENINVOICE_PROD_API_KEY", "")
    greeninvoice_prod_api_secret: str = os.getenv("GREENINVOICE_PROD_API_SECRET", "")
    greeninvoice_prod_base_url: str = os.getenv("GREENINVOICE_PROD_BASE_URL", "https://api.greeninvoice.co.il/api/v1")

    greeninvoice_delivery_doc_type: str = os.getenv("GREENINVOICE_DELIVERY_DOC_TYPE", "")
    greeninvoice_tax_invoice_doc_type: str = os.getenv("GREENINVOICE_TAX_INVOICE_DOC_TYPE", "305")

    google_service_account_json: str = _env_or_fallback("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    google_drive_oauth_client_json: str = _env_or_fallback("GOOGLE_DRIVE_OAUTH_CLIENT_JSON", "")
    google_drive_oauth_token_json: str = _env_or_fallback("GOOGLE_DRIVE_OAUTH_TOKEN_JSON", "")
    google_drive_oauth_redirect_uri: str = _env_or_fallback("GOOGLE_DRIVE_OAUTH_REDIRECT_URI", f"{DEFAULT_PUBLIC_BASE_URL}/google-drive/oauth/callback")
    gmail_oauth_client_json: str = _env_or_fallback("GMAIL_OAUTH_CLIENT_JSON", "")
    gmail_oauth_token_json: str = _env_or_fallback("GMAIL_OAUTH_TOKEN_JSON", "")
    gmail_oauth_redirect_uri: str = _env_or_fallback("GMAIL_OAUTH_REDIRECT_URI", f"{DEFAULT_PUBLIC_BASE_URL}/gmail-oauth/callback")
    google_sheets_spreadsheet_id: str = _env_or_fallback("GOOGLE_SHEETS_SPREADSHEET_ID", "")
    google_sheets_range: str = _env_or_fallback("GOOGLE_SHEETS_RANGE", "תשלומים והעברות 2026!A:M")
    google_sheets_inventory_raw_tab: str = os.getenv("GOOGLE_SHEETS_INVENTORY_RAW_TAB", "טבלת מלאי - חומרי גלם")
    google_sheets_inventory_finish_tab: str = os.getenv("GOOGLE_SHEETS_INVENTORY_FINISH_TAB", "טבלת מלאי - גמר")
    google_sheets_inventory_contacts_tab: str = os.getenv("GOOGLE_SHEETS_INVENTORY_CONTACTS_TAB", "אנשי קשר")
    google_sheets_project_managers_tab: str = os.getenv("GOOGLE_SHEETS_PROJECT_MANAGERS_TAB", "מנהלי פרויקטים")
    google_sheets_delivery_confirmations_tab: str = os.getenv("GOOGLE_SHEETS_DELIVERY_CONFIRMATIONS_TAB", "אישורי מסירה")
    google_sheets_delivery_contacts_tab: str = os.getenv("GOOGLE_SHEETS_DELIVERY_CONTACTS_TAB", "אנשי קשר הנה\"ח")
    google_sheets_customers_tab: str = os.getenv("GOOGLE_SHEETS_CUSTOMERS_TAB", "לקוחות")
    google_sheets_inactive_customers_tab: str = os.getenv("GOOGLE_SHEETS_INACTIVE_CUSTOMERS_TAB", "לקוחות לא פעילים")
    google_sheets_order_history_tab: str = os.getenv("GOOGLE_SHEETS_ORDER_HISTORY_TAB", "היסטוריה")
    google_sheets_quote_history_tab: str = os.getenv("GOOGLE_SHEETS_QUOTE_HISTORY_TAB", "היסטוריית הצעות מחיר")
    google_sheets_pazomat_tab: str = os.getenv("GOOGLE_SHEETS_PAZOMAT_TAB", "פזומט")
    google_sheets_sibus_tab: str = os.getenv("GOOGLE_SHEETS_SIBUS_TAB", "סיבוס")
    google_sheets_working_orders_tab: str = os.getenv("GOOGLE_SHEETS_WORKING_ORDERS_TAB", "הזמנות בעבודה")
    google_sheets_supplier_delivery_notes_tab: str = os.getenv("GOOGLE_SHEETS_SUPPLIER_DELIVERY_NOTES_TAB", "תעודות משלוח ספקים")
    google_sheets_inventory_purchase_orders_tab: str = os.getenv("GOOGLE_SHEETS_INVENTORY_PURCHASE_ORDERS_TAB", "הזמנות רכש")
    google_sheets_pricing_items_tab: str = os.getenv("GOOGLE_SHEETS_PRICING_ITEMS_TAB", "תמחור - פריטים")
    google_sheets_pricing_components_tab: str = os.getenv("GOOGLE_SHEETS_PRICING_COMPONENTS_TAB", "תמחור - עצי מוצר")
    google_sheets_marketing_notes_tab: str = os.getenv("GOOGLE_SHEETS_MARKETING_NOTES_TAB", "שיווק - הערות")
    google_sheets_marketing_reminders_tab: str = os.getenv("GOOGLE_SHEETS_MARKETING_REMINDERS_TAB", "שיווק - תזכורות")
    google_sheets_marketing_history_tab: str = os.getenv("GOOGLE_SHEETS_MARKETING_HISTORY_TAB", "שיווק - היסטוריה")
    google_sheets_marketing_pipeline_tab: str = os.getenv("GOOGLE_SHEETS_MARKETING_PIPELINE_TAB", "שיווק - לקוחות בתהליך שיווק")
    google_sheets_marketing_work_managers_tab: str = os.getenv("GOOGLE_SHEETS_MARKETING_WORK_MANAGERS_TAB", "שיווק - מאגר מנהלי עבודה")
    google_sheets_marketing_construction_companies_tab: str = os.getenv("GOOGLE_SHEETS_MARKETING_CONSTRUCTION_COMPANIES_TAB", "שיווק - מאגר חברות בנייה")
    google_sheets_finance_invoices_tab: str = os.getenv("GOOGLE_SHEETS_FINANCE_INVOICES_TAB", "כספים - חשבוניות")
    google_sheets_finance_settings_tab: str = os.getenv("GOOGLE_SHEETS_FINANCE_SETTINGS_TAB", "כספים - הגדרות")
    google_sheets_finance_customer_withholdings_tab: str = os.getenv("GOOGLE_SHEETS_FINANCE_CUSTOMER_WITHHOLDINGS_TAB", "כספים - ניכויי מס לקוחות")
    google_sheets_finance_bank_movements_tab: str = os.getenv("GOOGLE_SHEETS_FINANCE_BANK_MOVEMENTS_TAB", "כספים - תנועות עו\"ש")
    google_sheets_hr_employees_tab: str = os.getenv("GOOGLE_SHEETS_HR_EMPLOYEES_TAB", "עובדים ושכר - עובדים")
    google_sheets_hr_payroll_tab: str = os.getenv("GOOGLE_SHEETS_HR_PAYROLL_TAB", "עובדים ושכר - שכר")
    google_sheets_hr_contributions_tab: str = os.getenv("GOOGLE_SHEETS_HR_CONTRIBUTIONS_TAB", "עובדים ושכר - הפרשות")
    google_sheets_hr_hours_tab: str = os.getenv("GOOGLE_SHEETS_HR_HOURS_TAB", "עובדים ושכר - שעות")
    google_sheets_hr_documents_tab: str = os.getenv("GOOGLE_SHEETS_HR_DOCUMENTS_TAB", "עובדים ושכר - מסמכים")
    google_sheets_hr_payslip_prep_history_tab: str = os.getenv("GOOGLE_SHEETS_HR_PAYSLIP_PREP_HISTORY_TAB", "עובדים ושכר - היסטוריית הפקה")
    google_drive_orders_root_folder_id: str = _env_or_fallback("GOOGLE_DRIVE_ORDERS_ROOT_FOLDER_ID", "11coH4pVbxi7cdS2vVRNg9hX5FZ_DYC7T")
    supabase_url: str = _env_or_fallback("SUPABASE_URL", DEFAULT_SUPABASE_URL)
    supabase_anon_key: str = _env_or_fallback("SUPABASE_ANON_KEY", DEFAULT_SUPABASE_ANON_KEY)
    supabase_service_role_key: str = _env_or_fallback("SUPABASE_SERVICE_ROLE_KEY", DEFAULT_SUPABASE_SERVICE_ROLE_KEY)
    supabase_schema: str = _env_or_fallback("SUPABASE_SCHEMA", "public")
    supabase_storage_bucket: str = _env_or_fallback("SUPABASE_STORAGE_BUCKET", "ben-yacov-files")
    smtp_host: str = _env_or_fallback("SMTP_HOST", "")
    smtp_port: int = int(_env_or_fallback("SMTP_PORT", "587") or 587)
    smtp_username: str = _env_or_fallback("SMTP_USERNAME", "")
    smtp_password: str = _env_or_fallback("SMTP_PASSWORD", "")
    smtp_from_email: str = _env_or_fallback("SMTP_FROM_EMAIL", "office@ben-yacov.com")
    smtp_from_name: str = _env_or_fallback("SMTP_FROM_NAME", "בן יעקב פתרונות טקסטיל")
    smtp_use_ssl: bool = (_env_or_fallback("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes", "on"))
    whatsapp_recipient: str = os.getenv("WHATSAPP_RECIPIENT", "0547720142")
    whatsapp_provider: str = _env_or_fallback("WHATSAPP_PROVIDER", "auto")
    whatsapp_meta_access_token: str = _env_or_fallback("WHATSAPP_META_ACCESS_TOKEN", "")
    whatsapp_meta_phone_number_id: str = _env_or_fallback("WHATSAPP_META_PHONE_NUMBER_ID", "")
    whatsapp_meta_api_version: str = _env_or_fallback("WHATSAPP_META_API_VERSION", "v23.0")
    whatsapp_twilio_account_sid: str = _env_or_fallback("WHATSAPP_TWILIO_ACCOUNT_SID", "")
    whatsapp_twilio_auth_token: str = _env_or_fallback("WHATSAPP_TWILIO_AUTH_TOKEN", "")
    whatsapp_twilio_from: str = _env_or_fallback("WHATSAPP_TWILIO_FROM", "")
    whatsapp_railway_url: str = _env_or_fallback("WHATSAPP_RAILWAY_URL", "")
    whatsapp_railway_secret: str = _env_or_fallback("WHATSAPP_RAILWAY_SECRET", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5-mini")
    greeninvoice_assistant_months_back: int = int(os.getenv("GREENINVOICE_ASSISTANT_MONTHS_BACK", "36"))
    greeninvoice_assistant_page_size: int = int(os.getenv("GREENINVOICE_ASSISTANT_PAGE_SIZE", "100"))
    greeninvoice_assistant_max_pages: int = int(os.getenv("GREENINVOICE_ASSISTANT_MAX_PAGES", "12"))


settings = Settings()
settings.app_public_base_url = (settings.app_public_base_url or DEFAULT_PUBLIC_BASE_URL).rstrip("/")
settings.backend_api_base_url = (settings.backend_api_base_url or settings.app_public_base_url or DEFAULT_PUBLIC_BASE_URL).rstrip("/")

if not settings.google_service_account_json or settings.google_service_account_json == "XXXXXXXXXXXXXXX":
    settings.google_service_account_json = _env_or_fallback("GOOGLE_SERVICE_ACCOUNT_JSON", "")

if not settings.google_sheets_spreadsheet_id or settings.google_sheets_spreadsheet_id == "XXXXXXXXXXXXXXX":
    settings.google_sheets_spreadsheet_id = _env_or_fallback("GOOGLE_SHEETS_SPREADSHEET_ID", "")

if not settings.google_sheets_range or settings.google_sheets_range == "XXXXXXXXXXXXXXX":
    settings.google_sheets_range = _env_or_fallback("GOOGLE_SHEETS_RANGE", "תשלומים והעברות 2026!A:M")

if (
    str(settings.supabase_url or "").strip()
    and str(settings.supabase_service_role_key or "").strip()
    and str(settings.data_backend or "").strip().lower() != "supabase"
):
    settings.data_backend = "supabase"


def get_mode_config(mode: str):
    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode in {"production", "prod", "live", "real", "אמיתי", "פרודקשן"}:
        return {
            "base_url": settings.greeninvoice_prod_base_url,
            "api_key": settings.greeninvoice_prod_api_key,
            "api_secret": settings.greeninvoice_prod_api_secret,
        }
    else:
        return {
            "base_url": settings.greeninvoice_sandbox_base_url,
            "api_key": settings.greeninvoice_sandbox_api_key,
            "api_secret": settings.greeninvoice_sandbox_api_secret,
        }
