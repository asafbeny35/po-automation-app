import re
import json
import copy
import time
from uuid import uuid4
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .config import settings
from .greeninvoice import GreenInvoiceClient, _canonical_income_customer_name
from . import supabase_store
from .google_service_account import build_service_account_credentials
from .runtime_paths import runtime_root

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_SHEET_ID_CACHE: dict[str, int | None] = {}
_PROJECT_MANAGERS_ROWS_CACHE: list[dict] = []
_DELIVERY_CONFIRMATION_ROWS_CACHE: list[dict] = []
_DELIVERY_CONTACT_ROWS_CACHE: list[dict] = []
_CUSTOMER_ROWS_CACHE: list[dict] = []
_INACTIVE_CUSTOMER_ROWS_CACHE: list[dict] = []
_ORDER_HISTORY_ROWS_CACHE: list[dict] = []
_QUOTE_HISTORY_ROWS_CACHE: list[dict] = []
_INSTALLATION_CASE_ROWS_CACHE: list[dict] = []
_INSTALLATION_VISIT_ROWS_CACHE: list[dict] = []
_PAZOMAT_ROWS_CACHE: list[dict] = []
_SIBUS_ROWS_CACHE: list[dict] = []
_WORKING_ORDER_ROWS_CACHE: list[dict] = []
_INVENTORY_PURCHASE_ORDER_ROWS_CACHE: list[dict] = []
_PRICING_ITEM_ROWS_CACHE: list[dict] = []
_PRICING_COMPONENT_ROWS_CACHE: list[dict] = []
_MARKETING_NOTES_ROWS_CACHE: list[dict] = []
_MARKETING_REMINDERS_ROWS_CACHE: list[dict] = []
_MARKETING_HISTORY_ROWS_CACHE: list[dict] = []
_MARKETING_PIPELINE_ROWS_CACHE: list[dict] = []
_MARKETING_WORK_MANAGERS_ROWS_CACHE: list[dict] = []
_MARKETING_CONSTRUCTION_COMPANIES_ROWS_CACHE: list[dict] = []
_FINANCE_INVOICE_ROWS_CACHE: list[dict] = []
_FINANCE_SETTINGS_ROWS_CACHE: list[dict] = []
_FINANCE_CUSTOMER_WITHHOLDINGS_ROWS_CACHE: list[dict] = []
_FINANCE_BANK_MOVEMENTS_ROWS_CACHE: list[dict] = []
_SUPPLIER_DELIVERY_NOTE_ROWS_CACHE: list[dict] = []
_SHEET_ENSURED_CACHE: set[str] = set()
_PAYMENTS_TRANSFER_STATE_CACHE: dict | None = None
_PAYMENTS_TRANSFER_STATE_CACHE_TS = 0.0
_PAYMENT_SCHEMA_ENSURED_AT: dict[str, float] = {}
_PROJECT_MANAGERS_ROWS_CACHE_TS = 0.0
_DELIVERY_CONFIRMATION_ROWS_CACHE_TS = 0.0
_DELIVERY_CONTACT_ROWS_CACHE_TS = 0.0
_CUSTOMER_ROWS_CACHE_TS = 0.0
_INACTIVE_CUSTOMER_ROWS_CACHE_TS = 0.0
_ORDER_HISTORY_ROWS_CACHE_TS = 0.0
_QUOTE_HISTORY_ROWS_CACHE_TS = 0.0
_INSTALLATION_CASE_ROWS_CACHE_TS = 0.0
_INSTALLATION_VISIT_ROWS_CACHE_TS = 0.0
_PAZOMAT_ROWS_CACHE_TS = 0.0
_SIBUS_ROWS_CACHE_TS = 0.0
_WORKING_ORDER_ROWS_CACHE_TS = 0.0
_INVENTORY_PURCHASE_ORDER_ROWS_CACHE_TS = 0.0
_PRICING_ITEM_ROWS_CACHE_TS = 0.0
_PRICING_COMPONENT_ROWS_CACHE_TS = 0.0
_MARKETING_NOTES_ROWS_CACHE_TS = 0.0
_MARKETING_REMINDERS_ROWS_CACHE_TS = 0.0
_MARKETING_HISTORY_ROWS_CACHE_TS = 0.0
_MARKETING_PIPELINE_ROWS_CACHE_TS = 0.0
_MARKETING_WORK_MANAGERS_ROWS_CACHE_TS = 0.0
_MARKETING_CONSTRUCTION_COMPANIES_ROWS_CACHE_TS = 0.0
_FINANCE_INVOICE_ROWS_CACHE_TS = 0.0
_FINANCE_SETTINGS_ROWS_CACHE_TS = 0.0
_FINANCE_CUSTOMER_WITHHOLDINGS_ROWS_CACHE_TS = 0.0
_FINANCE_BANK_MOVEMENTS_ROWS_CACHE_TS = 0.0
_SUPPLIER_DELIVERY_NOTE_ROWS_CACHE_TS = 0.0
_INVENTORY_ROWS_CACHE: dict[str, list[dict]] = {}
_INVENTORY_ROWS_CACHE_TS: dict[str, float] = {}
_SPREADSHEET_METADATA_CACHE: dict | None = None
_SPREADSHEET_METADATA_CACHE_TS = 0.0
_CACHE_ROOT = runtime_root()
_LOG_CACHE_ROOT = _CACHE_ROOT / "logs"
_LOG_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
_PROJECT_MANAGERS_CACHE_FILE = _CACHE_ROOT / "project_managers_cache.json"
_DELIVERY_CONFIRMATION_CACHE_FILE = _CACHE_ROOT / "delivery_confirmations_cache.json"
_DELIVERY_CONTACTS_CACHE_FILE = _CACHE_ROOT / "delivery_contacts_cache.json"
_DELIVERY_CONFIRMATION_SUPPRESSIONS_FILE = _CACHE_ROOT / "delivery_confirmation_suppressions.json"
_CUSTOMERS_CACHE_FILE = _CACHE_ROOT / "customers_cache.json"
_INACTIVE_CUSTOMERS_CACHE_FILE = _CACHE_ROOT / "inactive_customers_cache.json"
_ORDER_HISTORY_CACHE_FILE = _CACHE_ROOT / "order_history_cache.json"
_QUOTE_HISTORY_CACHE_FILE = _CACHE_ROOT / "quote_history_cache.json"
_INSTALLATION_CASES_CACHE_FILE = _CACHE_ROOT / "installation_cases_cache.json"
_INSTALLATION_VISITS_CACHE_FILE = _CACHE_ROOT / "installation_visits_cache.json"
_PAZOMAT_CACHE_FILE = _CACHE_ROOT / "pazomat_cache.json"
_SIBUS_CACHE_FILE = _CACHE_ROOT / "sibus_cache.json"
_WORKING_ORDER_CACHE_FILE = _CACHE_ROOT / "working_orders_cache.json"
_INVENTORY_PURCHASE_ORDER_CACHE_FILE = _CACHE_ROOT / "inventory_purchase_orders_cache.json"
_PRICING_ITEMS_CACHE_FILE = _CACHE_ROOT / "pricing_items_cache.json"
_PRICING_COMPONENTS_CACHE_FILE = _CACHE_ROOT / "pricing_components_cache.json"
_MARKETING_NOTES_CACHE_FILE = _CACHE_ROOT / "marketing_notes_cache.json"
_MARKETING_REMINDERS_CACHE_FILE = _CACHE_ROOT / "marketing_reminders_cache.json"
_MARKETING_HISTORY_CACHE_FILE = _CACHE_ROOT / "marketing_history_cache.json"
_MARKETING_PIPELINE_CACHE_FILE = _CACHE_ROOT / "marketing_pipeline_cache.json"
_MARKETING_WORK_MANAGERS_CACHE_FILE = _CACHE_ROOT / "marketing_work_managers_cache.json"
_MARKETING_CONSTRUCTION_COMPANIES_CACHE_FILE = _CACHE_ROOT / "marketing_construction_companies_cache.json"
_FINANCE_INVOICES_CACHE_FILE = _CACHE_ROOT / "finance_invoices_cache.json"
_FINANCE_SETTINGS_CACHE_FILE = _CACHE_ROOT / "finance_settings_cache.json"
_FINANCE_CUSTOMER_WITHHOLDINGS_CACHE_FILE = _CACHE_ROOT / "finance_customer_withholdings_cache.json"
_FINANCE_BANK_MOVEMENTS_CACHE_FILE = _CACHE_ROOT / "finance_bank_movements_cache.json"
_SUPPLIER_DELIVERY_NOTE_CACHE_FILE = _CACHE_ROOT / "supplier_delivery_notes_cache.json"
_PAYMENTS_TRANSFER_CACHE_FILE = _CACHE_ROOT / "payments_transfer_cache.json"
_PAYMENTS_PAID_REPAIR_BACKUP_FILE = _LOG_CACHE_ROOT / "payment_paid_repair_backup_2026-04-17.json"
_PAYMENTS_TRANSFER_CACHE_TTL_SECONDS = 20
_PAYMENT_SCHEMA_CACHE_TTL_SECONDS = 900
_GENERIC_SHEET_CACHE_TTL_SECONDS = 20
_SPREADSHEET_METADATA_CACHE_TTL_SECONDS = 60
FORBIDDEN_PROJECT_MANAGER_PHONES = {
    "0547720142",
    "0505204010",
    "0503011503",
    "547720142",
    "505204010",
    "503011503",
}

_MARKETING_SUPABASE_DOMAINS = {
    "pipeline": "marketing_pipeline",
    "history": "marketing_history",
    "reminders": "marketing_reminders",
    "work_managers": "marketing_work_managers",
    "construction_companies": "marketing_construction_companies",
    "finance_invoices": "finance_invoices",
    "finance_settings": "finance_settings",
    "finance_customer_withholdings": "finance_customer_withholdings",
    "finance_bank_movements": "finance_bank_movements",
}


def _supabase_enabled_for(domain: str) -> bool:
    return supabase_store.is_enabled() and supabase_store.supports_domain(domain)


def _supabase_domain_for_marketing_kind(kind: str) -> str | None:
    domain = _MARKETING_SUPABASE_DOMAINS.get(kind)
    if not domain or not _supabase_enabled_for(domain):
        return None
    return domain


def _supabase_domain_for_inventory_kind(kind: str) -> str | None:
    domain = {
        "raw": "inventory_raw",
        "finish": "inventory_finish",
        "contacts": "inventory_contacts",
    }.get(kind)
    if not domain or not _supabase_enabled_for(domain):
        return None
    return domain


def _supabase_domain_for_pricing_kind(kind: str) -> str | None:
    domain = {
        "items": "pricing_items",
        "components": "pricing_components",
    }.get(kind)
    if not domain or not _supabase_enabled_for(domain):
        return None
    return domain

RAW_INVENTORY_HEADERS = [
    "ספק",
    "מק״ט ספק",
    "מוצר",
    "חומר",
    "אורך",
    "רוחב",
    "עובי",
    "מחיר",
    "יחידה",
    "כמות בפועל",
    "תאריך עדכון",
    "הערות",
    "כמות ליחידה",
]

FINISH_INVENTORY_HEADERS = [
    "מוצר",
    "רוחב",
    "אורך",
    "כמות בפועל",
    "תאריך עדכון",
    "הערות",
]

CONTACTS_HEADERS = [
    "חברה",
    "שם",
    "טלפון חברה",
    "טלפון ישיר",
    "כתובת מייל",
]

SUPPLIER_DELIVERY_NOTE_HEADERS = [
    "מזהה רשומה",
    "שם ספק",
    "שם פרסר",
    "שם קובץ מקור",
    "מספר תעודת משלוח",
    "תאריך תעודה",
    "שם לקוח",
    "ח.פ / ת.ז לקוח",
    "כתובת אספקה",
    "איש קשר",
    "טלפון איש קשר",
    "מספר שורה",
    "מק\"ט ספק",
    "תיאור פריט",
    "מוצר",
    "חומר",
    "אורך",
    "רוחב",
    "עובי",
    "כמות",
    "יחידה",
    "הערות",
    "נתיב קובץ מקומי",
    "מזהה קובץ מקור בדרייב",
    "קישור קובץ מקור בדרייב",
    "עודכן לאחרונה",
]

INVENTORY_PURCHASE_ORDER_HEADERS = [
    "מזהה היסטוריה",
    "נוצר בתאריך",
    "סביבה",
    "שם ספק",
    "ח.פ / ע.מ ספק",
    "מייל ספק",
    "טלפון ספק",
    "מספר הזמנת רכש",
    "מזהה מסמך בחשבונית ירוקה",
    "תאריך הזמנה",
    "תיאור פריט",
    "מק\"ט פריט",
    "כמות",
    "יחידה",
    "מחיר יחידה",
    "סכום ביניים",
    "מע\"מ",
    "סה\"כ",
    "הערות",
    "נתיב קובץ מקומי",
    "מזהה קובץ בדרייב",
    "קישור קובץ בדרייב",
    "מזהה תיקיית דרייב",
    "קישור תיקיית דרייב",
    "סטטוס שליחה",
    "נשלח בתאריך",
    "עודכן לאחרונה",
]

WORKING_ORDER_HEADERS = [
    "מזהה רשומה",
    "נוצר בתאריך",
    "עודכן לאחרונה",
    "שם קובץ מקור",
    "נתיב קובץ מקור",
    "תאריך הזמנה",
    "שם לקוח",
    "ח.פ / ע.מ לקוח",
    "אימייל לקוח",
    "טלפון לקוח",
    "כתובת אספקה",
    "פרויקט",
    "איש קשר",
    "טלפון איש קשר",
    "תנאי תשלום ימים",
    "תנאי תשלום טקסט",
    "מספר הזמנה",
    "תיאור פריט",
    "מק\"ט פריט",
    "יחידה",
    "כמות",
    "מחיר יחידה",
    "סכום ביניים",
    "מע\"מ",
    "סה\"כ",
    "מספר פריטים",
    "JSON פריטים",
    "JSON Payload",
    "מזהה קובץ בדרייב",
    "קישור קובץ בדרייב",
    "מזהה תיקיית דרייב",
    "קישור תיקיית דרייב",
    "כולל התקנה",
    "הערות להזמנה",
    "שם קובץ הערה",
    "נתיב קובץ הערה",
    "מזהה קובץ הערה בדרייב",
    "קישור קובץ הערה בדרייב",
]

DELIVERY_CONFIRMATION_HEADERS = [
    "תאריך הזמנה",
    "שם חברה",
    "מספר הזמנה",
    "תאריך הפקה",
    "מספר חשבונית מס",
    "סכום הזמנה",
    "מייל יעד",
    "תעודת משלוח חתומה",
    "נתיב קובץ חתום",
    "מזהה דרייב קובץ חתום",
    "מזהה דרייב חשבונית",
    "שם מסמך COC",
    "מזהה דרייב COC",
    "מזהה תיקיית דרייב",
    "קישור תיקיית דרייב",
    "מזהה מימוש",
    "מזהה היסטוריה",
    "מצב מסמך",
    "מספר תעודת משלוח",
    "מזהה תעודת משלוח",
    "נשלח אישור מסירה",
    "נשלח בתאריך",
    "עודכן לאחרונה",
    "סביבה",
]

DELIVERY_CONTACT_HEADERS = [
    "שם החברה",
    "איש קשר הנה\"ח",
    "טלפון",
    "נייד",
    "דואר אלקטרוני",
    "עודכן לאחרונה",
]

RAW_INVENTORY_FIELDS = [
    "supplier",
    "supplier_sku",
    "product",
    "material",
    "length",
    "width",
    "thickness",
    "price",
    "unit",
    "actual_quantity",
    "updated_at",
    "notes",
    "unit_count",
]

FINISH_INVENTORY_FIELDS = [
    "product",
    "width",
    "length",
    "actual_quantity",
    "updated_at",
    "notes",
]

CONTACTS_FIELDS = [
    "company",
    "name",
    "company_phone",
    "direct_phone",
    "email",
]

SUPPLIER_DELIVERY_NOTE_FIELDS = [
    "record_id",
    "supplier_name",
    "parser_name",
    "source_document_name",
    "delivery_note_number",
    "delivery_date",
    "customer_name",
    "customer_id",
    "delivery_address",
    "contact_name",
    "contact_phone",
    "item_index",
    "supplier_sku",
    "item_description",
    "product",
    "material",
    "length",
    "width",
    "thickness",
    "quantity",
    "unit",
    "notes",
    "source_local_path",
    "source_drive_file_id",
    "source_drive_url",
    "updated_at",
]

INVENTORY_PURCHASE_ORDER_FIELDS = [
    "history_id",
    "created_at",
    "mode",
    "supplier_name",
    "supplier_id",
    "supplier_email",
    "supplier_phone",
    "po_number",
    "po_document_id",
    "po_date",
    "item_description",
    "item_sku",
    "item_quantity",
    "item_unit",
    "item_unit_price",
    "subtotal",
    "vat",
    "total",
    "remarks",
    "po_local_file",
    "po_drive_file_id",
    "po_drive_url",
    "drive_folder_id",
    "drive_folder_url",
    "send_status",
    "sent_at",
    "updated_at",
]

WORKING_ORDER_FIELDS = [
    "row_id",
    "created_at",
    "updated_at",
    "source_file_name",
    "source_file_path",
    "po_date",
    "customer_name",
    "customer_id",
    "customer_email",
    "customer_phone",
    "delivery_address",
    "project",
    "contact_name",
    "contact_phone",
    "payment_terms_days",
    "payment_terms_label",
    "po_number",
    "item_description",
    "item_sku",
    "item_unit",
    "item_quantity",
    "item_unit_price",
    "subtotal",
    "vat",
    "total",
    "items_count",
    "items_json",
    "payload_json",
    "drive_file_id",
    "drive_url",
    "drive_folder_id",
    "drive_folder_url",
    "requires_installation",
    "order_note_text",
    "order_note_file_name",
    "order_note_file_path",
    "order_note_drive_file_id",
    "order_note_drive_url",
]

PRICING_ITEM_HEADERS = [
    "מזהה פריט",
    "סוג",
    "שם פריט",
    "יחידת תמחור",
    "רוחב ברירת מחדל (מ')",
    "אורך ברירת מחדל (מ')",
    "דקות עבודה",
    "עלות שעת עבודה",
    "עלות משלוח כוללת",
    "כמות להזמנה",
    "מזהה מידה נבחרת",
    "JSON מידות",
    "הערות",
    "פעיל",
    "עודכן לאחרונה",
]

PRICING_ITEM_FIELDS = [
    "item_id",
    "kind",
    "name",
    "pricing_unit",
    "default_width_m",
    "default_length_m",
    "labor_minutes",
    "labor_hour_cost",
    "shipping_total",
    "shipping_divisor",
    "selected_dimension_id",
    "dimensions_json",
    "notes",
    "active",
    "updated_at",
]

PRICING_COMPONENT_HEADERS = [
    "מזהה רכיב",
    "מזהה פריט",
    "סדר שורה",
    "סוג רכיב",
    "מפתח חומר גלם",
    "שם ספק",
    "מק״ט ספק",
    "מוצר במלאי",
    "חומר",
    "אורך",
    "רוחב",
    "עובי",
    "יחידה",
    "כמות ליחידה",
    "כמות שימוש",
    "בסיס שימוש",
    "קבוצת אפשרויות",
    "אחוז פחת",
    "הערות",
    "עודכן לאחרונה",
]

PRICING_COMPONENT_FIELDS = [
    "component_id",
    "item_id",
    "line_order",
    "component_kind",
    "inventory_key",
    "supplier",
    "supplier_sku",
    "inventory_product",
    "material",
    "length",
    "width",
    "thickness",
    "unit",
    "unit_count",
    "consumption_quantity",
    "consumption_basis",
    "option_group",
    "waste_percent",
    "notes",
    "updated_at",
]

DELIVERY_CONFIRMATION_FIELDS = [
    "order_date",
    "company",
    "po_number",
    "invoice_date",
    "tax_invoice_number",
    "order_total",
    "target_email",
    "signed_delivery_name",
    "signed_delivery_local_path",
    "signed_delivery_drive_file_id",
    "invoice_drive_file_id",
    "coc_name",
    "coc_drive_file_id",
    "order_drive_folder_id",
    "order_drive_folder_url",
    "fulfillment_id",
    "history_id",
    "document_mode",
    "delivery_document_number",
    "delivery_document_id",
    "sent",
    "sent_at",
    "updated_at",
    "source_mode",
]

DELIVERY_CONTACT_FIELDS = [
    "company",
    "accounting_contact_name",
    "phone",
    "mobile",
    "email",
    "updated_at",
]

DELIVERY_CONTACT_EMAIL_OVERRIDES_BY_COMPANY = {
    'קידר מבנים בע"מ': "sapakimliraz@kedar-mivnim.com",
}

ORDER_HISTORY_HEADERS = [
    "מזהה היסטוריה",
    "תאריך ושעה",
    "מקור",
    "סביבה",
    "שם לקוח",
    "ח.פ / ע.מ",
    "דוא\"ל לקוח",
    "טלפון לקוח",
    "כתובת אספקה",
    "פרויקט",
    "איש קשר",
    "טלפון איש קשר",
    "שוטף + ימים",
    "תיאור תנאי תשלום",
    "מספר הזמנת רכש",
    "מספר הצעת מחיר",
    "מזהה מימוש",
    "סוג מסמכים",
    "תגית סטטוס",
    "מספר תעודת משלוח",
    "מזהה תעודת משלוח",
    "מספר חשבונית מס",
    "מזהה חשבונית מס",
    "תיאור פריט",
    "מק\"ט",
    "יחידה",
    "כמות",
    "מחיר יחידה",
    "סכום שורה",
    "סכום ביניים",
    "מע\"מ",
    "סה\"כ",
    "טקסט תחתון",
    "שורות חלוקת מדבקות",
    "מזהה תיקיית דרייב",
    "קישור תיקיית דרייב",
    "מזהה קובץ תעודת משלוח ב-Drive",
    "מזהה קובץ חשבונית ב-Drive",
    "מזהה קובץ ממוזג ב-Drive",
    "מזהה קובץ COC ב-Drive",
    "קישורי מסמכים",
    "נשלח אישור מסירה",
    "עודכן לאחרונה",
    "תאריך הזמנת רכש",
    "JSON פריטים",
    "JSON פריטים מקוריים",
    "אספקה חלקית",
    "מזהה שורש אספקה חלקית",
]

ORDER_HISTORY_FIELDS = [
    "history_id",
    "created_at",
    "input_source",
    "mode",
    "customer_name",
    "customer_id",
    "customer_email",
    "customer_phone",
    "delivery_address",
    "project",
    "contact_name",
    "contact_phone",
    "payment_terms_days",
    "payment_terms_label",
    "po_number",
    "quote_number",
    "fulfillment_id",
    "document_mode",
    "order_status_tag",
    "delivery_document_number",
    "delivery_document_id",
    "tax_invoice_number",
    "tax_invoice_document_id",
    "item_description",
    "item_sku",
    "item_unit",
    "item_quantity",
    "item_unit_price",
    "item_line_total",
    "subtotal",
    "vat",
    "total",
    "footer_text",
    "label_split_rows_json",
    "order_drive_folder_id",
    "order_drive_folder_url",
    "delivery_drive_file_id",
    "invoice_drive_file_id",
    "merged_drive_file_id",
    "coc_drive_file_id",
    "document_links_json",
    "delivery_confirmation_sent",
    "updated_at",
    "po_date",
    "items_json",
    "ordered_items_json",
    "requires_installation",
    "partial_delivery",
    "partial_root_history_id",
]

INSTALLATION_CASE_HEADERS = [
    "מזהה התקנה",
    "מזהה שורש הזמנה",
    "מזהה היסטוריה נוכחי",
    "תאריך יצירה",
    "עודכן לאחרונה",
    "מקור",
    "מספר הזמנת רכש",
    "תאריך הזמנת רכש",
    "שם לקוח",
    "ח.פ / ע.מ",
    "דוא\"ל לקוח",
    "טלפון לקוח",
    "כתובת אספקה",
    "פרויקט",
    "איש קשר",
    "טלפון איש קשר",
    "שוטף + ימים",
    "תיאור תנאי תשלום",
    "סטטוס",
    "סיבת עיכוב",
    "תאריך ביקור הבא",
    "תאריך ביקור אחרון",
    "מספר ביקורים",
    "הערות",
    "מזהה תיקיית דרייב",
    "קישור תיקיית דרייב",
    "מזהה קובץ הזמנת רכש",
    "קישור הזמנת רכש",
    "מספר תעודת משלוח",
    "מזהה תעודת משלוח",
    "מספר חשבונית מס",
    "מזהה חשבונית מס",
    "מזהה קובץ תעודת משלוח ב-Drive",
    "מזהה קובץ חשבונית ב-Drive",
    "מזהה קובץ ממוזג ב-Drive",
    "מזהה קובץ COC ב-Drive",
    "קישורי מסמכים",
    "JSON פריטים להתקנה",
    "JSON פריטים שהותקנו",
    "JSON פריטים שנותרו",
    "סה\"כ כמות בהזמנה",
    "סה\"כ הותקן",
    "סה\"כ נותר",
    "פעיל במקור",
    "סונכרן לאחרונה",
]

INSTALLATION_CASE_FIELDS = [
    "installation_id",
    "root_history_id",
    "source_history_id",
    "created_at",
    "updated_at",
    "source_mode",
    "po_number",
    "po_date",
    "customer_name",
    "customer_id",
    "customer_email",
    "customer_phone",
    "delivery_address",
    "project",
    "contact_name",
    "contact_phone",
    "payment_terms_days",
    "payment_terms_label",
    "status",
    "delay_reason",
    "next_visit_date",
    "last_visit_date",
    "visit_count",
    "notes",
    "order_drive_folder_id",
    "order_drive_folder_url",
    "source_po_drive_file_id",
    "source_po_drive_url",
    "delivery_document_number",
    "delivery_document_id",
    "tax_invoice_number",
    "tax_invoice_document_id",
    "delivery_drive_file_id",
    "invoice_drive_file_id",
    "merged_drive_file_id",
    "coc_drive_file_id",
    "document_links_json",
    "install_items_json",
    "installed_items_json",
    "remaining_items_json",
    "total_ordered_quantity",
    "total_installed_quantity",
    "total_remaining_quantity",
    "source_active",
    "last_sync_at",
]

INSTALLATION_VISIT_HEADERS = [
    "מזהה ביקור",
    "מזהה התקנה",
    "תאריך יצירה",
    "עודכן לאחרונה",
    "תאריך ביקור",
    "תאריך מתוזמן",
    "סטטוס",
    "JSON פריטים שהותקנו",
    "סה\"כ כמות שהותקנה",
    "הערות",
    "סיכום קצר",
]

INSTALLATION_VISIT_FIELDS = [
    "visit_id",
    "installation_id",
    "created_at",
    "updated_at",
    "visit_date",
    "scheduled_date",
    "status",
    "installed_items_json",
    "installed_total_quantity",
    "notes",
    "summary_text",
]

QUOTE_HISTORY_HEADERS = [
    "מזהה היסטוריה",
    "תאריך ושעה",
    "מקור",
    "סביבה",
    "שם לקוח",
    "ח.פ / ע.מ",
    "מספר הזמנת רכש",
    "מספר הצעת מחיר",
    "מזהה מסמך הצעת מחיר",
    "תאריך הצעת מחיר",
    "דוא\"ל לקוח",
    "טלפון לקוח",
    "כתובת אספקה",
    "פרויקט",
    "איש קשר",
    "טלפון איש קשר",
    "שוטף + ימים",
    "תיאור תנאי תשלום",
    "תיאור פריט",
    "מק\"ט",
    "יחידה",
    "כמות",
    "מחיר יחידה",
    "סכום שורה",
    "סכום ביניים",
    "מע\"מ",
    "סה\"כ",
    "הערות למסמכים",
    "JSON פריטים",
    "חלוקה למדבקות",
    "מזהה תיקיית דרייב",
    "קישור תיקיית דרייב",
    "קישורי מסמכים",
    "סטטוס שליחת מייל",
    "מייל נשלח בתאריך",
    "עודכן לאחרונה",
]

QUOTE_HISTORY_FIELDS = [
    "history_id",
    "created_at",
    "input_source",
    "mode",
    "customer_name",
    "customer_id",
    "po_number",
    "quote_number",
    "quote_document_id",
    "quote_date",
    "customer_email",
    "customer_phone",
    "delivery_address",
    "project",
    "contact_name",
    "contact_phone",
    "payment_terms_days",
    "payment_terms_label",
    "item_description",
    "item_sku",
    "item_unit",
    "item_quantity",
    "item_unit_price",
    "item_line_total",
    "subtotal",
    "vat",
    "total",
    "footer_text",
    "items_json",
    "label_split_rows_json",
    "quote_drive_folder_id",
    "quote_drive_folder_url",
    "document_links_json",
    "quote_mail_status",
    "quote_mail_sent_at",
    "updated_at",
]

PAZOMAT_HEADERS = [
    "חודש",
    "סטטוס",
    "מזהה הודעת Gmail",
    "נושא",
    "סוג מקור",
    "מספר חשבונית",
    "מספר מסמך דלק",
    "סה\"כ חיוב",
    "חיוב דלק",
    "דמי שירות",
    "תאריך חיוב",
    "מספר רכבים",
    "רכבים",
    "מספר כרטיסים",
    "כרטיסי תדלוק",
    "סה\"כ ליטרים",
    "מזהה תיקיית Drive",
    "קישור תיקיית Drive",
    "מזהה קובץ Drive",
    "קישור לחשבונית",
    "נתיב קובץ מקומי",
    "הערות",
    "עודכן לאחרונה",
]

PAZOMAT_FIELDS = [
    "month",
    "status",
    "gmail_message_id",
    "subject",
    "source_type",
    "invoice_number",
    "fuel_doc_number",
    "total_amount",
    "fuel_amount",
    "service_amount",
    "debit_date",
    "vehicle_count",
    "vehicles_json",
    "card_count",
    "cards_json",
    "liters_total",
    "drive_folder_id",
    "drive_folder_url",
    "drive_file_id",
    "drive_url",
    "local_path",
    "notes",
    "updated_at",
]

SIBUS_HEADERS = [
    "חודש",
    "סטטוס",
    "מזהה הודעת Gmail",
    "נושא",
    "סוג מקור",
    "מספר חשבונית",
    "תאריך חשבונית",
    "תקופת חיוב",
    "לתשלום עד",
    "סכום לפני מע\"מ",
    "מע\"מ",
    "סה\"כ חיוב",
    "מספר לקוח",
    "מזהה תיקיית Drive",
    "קישור תיקיית Drive",
    "מזהה קובץ Drive",
    "קישור לחשבונית",
    "נתיב קובץ מקומי",
    "הערות",
    "עודכן לאחרונה",
]

SIBUS_FIELDS = [
    "month",
    "status",
    "gmail_message_id",
    "subject",
    "source_type",
    "invoice_number",
    "invoice_date",
    "billing_period",
    "due_date",
    "subtotal_amount",
    "vat_amount",
    "total_amount",
    "customer_number",
    "drive_folder_id",
    "drive_folder_url",
    "drive_file_id",
    "drive_url",
    "local_path",
    "notes",
    "updated_at",
]

MARKETING_NOTE_HEADERS = [
    "מפתח לקוח",
    "מזהה לקוח",
    "ח.פ / ת.ז",
    "שם לקוח",
    "הערה",
    "עודכן לאחרונה",
]

MARKETING_NOTE_FIELDS = [
    "customer_key",
    "customer_guid",
    "customer_id",
    "customer_name",
    "note_text",
    "updated_at",
]

MARKETING_REMINDER_HEADERS = [
    "מזהה תזכורת",
    "מפתח לקוח",
    "מזהה לקוח",
    "ח.פ / ת.ז",
    "שם לקוח",
    "איש קשר",
    "טלפון",
    "דוא\"ל",
    "הערות",
    "לתאריך",
    "בשעה",
    "סטטוס",
    "ערוץ",
    "תוכן",
    "סטטוס שליחה",
    "נשלח לאחרונה",
    "סטטוס תזכורת אוטומטית",
    "תזכורת אוטומטית נשלחה",
    "נוצר בתאריך",
    "טופל בתאריך",
]

MARKETING_REMINDER_FIELDS = [
    "reminder_id",
    "customer_key",
    "customer_guid",
    "customer_id",
    "customer_name",
    "contact_name",
    "phone",
    "emails",
    "note_text",
    "due_date",
    "due_time",
    "status",
    "channel",
    "message",
    "comm_status",
    "comm_sent_at",
    "auto_whatsapp_status",
    "auto_whatsapp_sent_at",
    "created_at",
    "completed_at",
]

MARKETING_HISTORY_HEADERS = [
    "מזהה אירוע",
    "תאריך ושעה",
    "מפתח לקוח",
    "מזהה לקוח",
    "ח.פ / ת.ז",
    "שם לקוח",
    "סוג פעולה",
    "ערוץ",
    "נושא",
    "פרטים",
    "תוצאה",
]

MARKETING_HISTORY_FIELDS = [
    "history_id",
    "created_at",
    "customer_key",
    "customer_guid",
    "customer_id",
    "customer_name",
    "action_type",
    "channel",
    "subject",
    "details_json",
    "result",
]

MARKETING_PIPELINE_HEADERS = [
    "מפתח לקוח",
    "מזהה לקוח",
    "ח.פ / ת.ז",
    "שם חברה",
    "מספר הצעת מחיר",
    "מזהה מסמך הצעת מחיר",
    "תאריך הצעה",
    "פריט",
    "דוא\"ל",
    "טלפון",
    "שם איש קשר",
    "הערות",
    "סטטוס שליחה",
    "נשלח לאחרונה",
    "נושא המייל האחרון",
    "תאריך שליחת המייל האחרון",
    "קישור דרייב להצעה",
    "מזהה קובץ דרייב",
    "קישור מקורי להצעה",
    "מקור",
    "עודכן לאחרונה",
]

MARKETING_PIPELINE_FIELDS = [
    "customer_key",
    "customer_guid",
    "customer_id",
    "customer_name",
    "quote_number",
    "quote_document_id",
    "quote_date",
    "item_name",
    "emails",
    "phone",
    "contact_name",
    "note_text",
    "comm_status",
    "comm_sent_at",
    "mail_subject",
    "mail_sent_at",
    "quote_drive_url",
    "quote_drive_file_id",
    "quote_source_url",
    "source",
    "updated_at",
]

MARKETING_WORK_MANAGER_HEADERS = [
    "מזהה רשומה",
    "שם מלא",
    "חברה",
    "דוא\"ל",
    "טלפון 1",
    "טלפון 2",
    "טלפון 3",
    "מינוי נוכחי",
    "מעסיק נוכחי",
    "מקום עבודה נוכחי",
    "דף פרטים",
    "קיים במנהלי פרויקטים",
    "נבדק מול מנהלי פרויקטים",
    "עודכן לאחרונה",
]

MARKETING_WORK_MANAGER_FIELDS = [
    "row_id",
    "full_name",
    "company_name",
    "email",
    "phone_1",
    "phone_2",
    "phone_3",
    "active_status",
    "current_employer",
    "current_workplace",
    "details_url",
    "project_manager_match",
    "project_manager_checked_at",
    "updated_at",
]

MARKETING_CONSTRUCTION_COMPANY_HEADERS = [
    "מזהה רשומה",
    "חברה",
    "ח.פ",
    "טלפון",
    "כתובת",
    "דוא\"ל",
    "אתר אינטרנט",
    "הערות",
    "עודכן לאחרונה",
]

MARKETING_CONSTRUCTION_COMPANY_FIELDS = [
    "row_id",
    "company_name",
    "company_id",
    "phone",
    "address",
    "email",
    "details_url",
    "notes",
    "updated_at",
]

FINANCE_INVOICE_HEADERS = [
    "מזהה רשומה",
    "תאריך",
    "ספק",
    "מספר אסמכתא",
    "מספר הקצאה",
    "מטבע",
    "שירות / מוצר",
    "סה\"כ (לפני מע\"מ)",
    "מע\"מ",
    "סה\"כ (כולל מע\"מ)",
    "שם קובץ מקור",
    "נתיב קובץ מקור",
    "תאריך דיווח",
    "מועדי דיווח נוספים",
    "מזהה קובץ Drive",
    "קישור לחשבונית",
    "עודכן לאחרונה",
]

FINANCE_INVOICE_FIELDS = [
    "row_id",
    "invoice_date",
    "supplier_name",
    "reference_number",
    "allocation_number",
    "currency_code",
    "service_or_product",
    "subtotal",
    "vat",
    "total",
    "source_file_name",
    "source_file_path",
    "report_due_date",
    "report_due_overrides",
    "drive_file_id",
    "drive_url",
    "updated_at",
]

FINANCE_SETTINGS_HEADERS = [
    "מפתח",
    "ערך",
    "עודכן לאחרונה",
]

FINANCE_SETTINGS_FIELDS = [
    "setting_key",
    "setting_value",
    "updated_at",
]

FINANCE_CUSTOMER_WITHHOLDINGS_HEADERS = [
    "מזהה שורה",
    "תאריך קבלה",
    "לקוח",
    "מספר חשבונית",
    "מספר קבלה",
    "בוצע ניכוי",
    "סכום מלא",
    "אחוז ניכוי",
    "סכום שנוכה",
    "סה\"כ ששולם",
    "סביבה",
    "ממתין לבדיקת מיגרציה",
    "מזהה אצוות מיגרציה",
    "עודכן בתאריך",
]

FINANCE_CUSTOMER_WITHHOLDINGS_FIELDS = [
    "row_id",
    "receipt_date",
    "customer_name",
    "invoice_number",
    "receipt_number",
    "withholding_applied",
    "gross_amount",
    "withholding_percent",
    "withheld_amount",
    "paid_amount",
    "source_mode",
    "review_pending",
    "migration_batch",
    "dismissed",
    "updated_at",
]

FINANCE_BANK_MOVEMENTS_HEADERS = [
    "מזהה שורה",
    "מספר חשבון",
    "שם חשבון",
    "חברה",
    "מקטע",
    "תאריך",
    "יום ערך",
    "תיאור התנועה",
    "סוג פעולה",
    "סכום",
    "יתרה",
    "אסמכתה",
    "עמלה / הערות",
    "ערוץ ביצוע",
    "שם קובץ מקור",
    "עודכן לאחרונה",
]

FINANCE_BANK_MOVEMENTS_FIELDS = [
    "row_id",
    "account_number",
    "account_name",
    "company_name",
    "section_name",
    "transaction_date",
    "value_date",
    "description",
    "operation_type",
    "amount",
    "balance",
    "reference",
    "fee_or_notes",
    "channel",
    "source_file_name",
    "updated_at",
]

CUSTOMER_HEADERS = [
    "מזהה לקוח",
    "שם לקוח",
    "ח.פ / ת.ז",
    "סביבה",
    "סטטוס",
    "שליחה",
    "מחלקה",
    "מפתח הנה\"ח",
    "שוטף +",
    "טלפון",
    "נייד",
    "מיילים",
    "איש קשר",
    "כתובת",
    "עיר",
    "מיקוד",
    "מדינה",
    "בנק",
    "סניף",
    "חשבון",
    "הערות",
    "סך הכנסות",
    "סך תשלומים",
    "יתרה",
    "נוצר בתאריך",
    "עודכן בתאריך",
    "תחום לקוח",
    "סונכרן לשיט",
    "עודכן בפרטי החשבון החדשים",
]

CUSTOMER_FIELDS = [
    "customer_guid",
    "customer_name",
    "customer_id",
    "source_mode",
    "active",
    "send",
    "department",
    "accounting_key",
    "payment_terms_days",
    "phone",
    "mobile",
    "emails",
    "contact_person",
    "address",
    "city",
    "zip",
    "country",
    "bank_name",
    "bank_branch",
    "bank_account",
    "remarks",
    "income_amount",
    "payment_amount",
    "balance_amount",
    "creation_date",
    "last_update_date",
    "customer_domain",
    "synced_at",
    "bank_details_updated_sent",
]


def _normalize_customer_source_mode(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"sb", "sandbox", "test", "טסט"}:
        return "SB"
    if lowered in {"prod", "production", "real", "live", "אמיתי"}:
        return "PROD"
    if lowered in {"drive", "drv"}:
        return "DRIVE"
    return str(value or "").strip().upper()


def _normalize_customer_domain(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"construction", "building", "construction_field", "תחום הבנייה", "בנייה", "הבניה"}:
        return "construction"
    if lowered in {"textile", "technical_textile", "textile_processing", "עיבוד טכני בטקסטיל"}:
        return "textile"
    if lowered in {"supplier", "vendor", "ספק", "ספקים"}:
        return "supplier"
    if lowered in {"graphic_web", "graphic_design", "web_design", "design_web", "עיצוב גרפי ואינטרנט", "עיצוב גרפי", "אינטרנט"}:
        return "graphic_web"
    return ""


def _customer_name_dedupe_key(value: str) -> str:
    canonical = _canonical_income_customer_name(value) or str(value or "").strip()
    canonical = canonical.replace("בנייה", "בניה")
    canonical = re.sub(r'["\'״׳\.\-,]', " ", canonical)
    canonical = re.sub(r"\bבעמ\b", " ", canonical)
    canonical = re.sub(r"\s+", " ", canonical).strip().lower()
    return canonical


def _customer_row_quality_score(row: dict) -> tuple[int, int]:
    mode = str(row.get("source_mode") or "").strip().upper()
    active = str(row.get("active") or "").strip().upper()
    score = 0
    if mode == "PROD":
        score += 70
    elif mode == "DRIVE":
        score += 55
    elif mode == "SB":
        score += 50
    if str(row.get("customer_guid") or "").strip():
        score += 40
    if str(row.get("customer_id") or "").strip():
        score += 25
    if active == "TRUE":
        score += 15
    elif active == "FALSE":
        score += 5
    score += sum(1 for value in row.values() if str(value or "").strip())
    return score, len(str(row.get("customer_name") or "").strip())


def _merge_customer_row_pair(preferred: dict, other: dict) -> dict:
    merged = dict(preferred or {})
    for field in CUSTOMER_FIELDS:
        current_value = str(merged.get(field, "") or "").strip()
        other_value = str((other or {}).get(field, "") or "").strip()
        if not current_value and other_value:
            merged[field] = other_value
    merged["source_mode"] = _normalize_customer_source_mode(merged.get("source_mode", ""))
    merged["active"] = _normalize_customer_bool(merged.get("active", ""))
    merged["send"] = _normalize_customer_bool(merged.get("send", ""))
    merged["customer_domain"] = _normalize_customer_domain(merged.get("customer_domain", ""))
    merged["emails"] = _normalize_customer_emails(merged.get("emails", ""))
    merged["customer_name"] = _canonical_income_customer_name(merged.get("customer_name", "")) or str(merged.get("customer_name") or "").strip()
    merged["customer_id"] = re.sub(r"\D+", "", str(merged.get("customer_id") or ""))
    merged["synced_at"] = str(merged.get("synced_at") or (other or {}).get("synced_at") or datetime.now().isoformat(timespec="seconds"))
    return merged


def _merge_customer_row_group(rows: list[dict]) -> dict:
    ordered = sorted(
        [dict(row) for row in (rows or []) if isinstance(row, dict)],
        key=_customer_row_quality_score,
        reverse=True,
    )
    if not ordered:
        return _normalize_customer_row({})
    merged = dict(ordered[0])
    for row in ordered[1:]:
        merged = _merge_customer_row_pair(merged, row)
    return _normalize_customer_row(merged)


def _dedupe_customer_rows(rows: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = {}
    passthrough: list[dict] = []
    for row in rows or []:
        normalized = _normalize_customer_row(row if isinstance(row, dict) else {})
        name_key = _customer_name_dedupe_key(normalized.get("customer_name", ""))
        id_key = re.sub(r"\D+", "", str(normalized.get("customer_id") or ""))
        if not name_key and not id_key:
            passthrough.append(normalized)
            continue
        groups.setdefault((name_key, id_key), []).append(normalized)

    deduped: list[dict] = []
    for group_rows in groups.values():
        grouped_by_mode: dict[str, list[dict]] = {}
        blank_mode_rows: list[dict] = []
        for row in group_rows:
            mode = str(row.get("source_mode") or "").strip().upper()
            if mode in {"PROD", "SB", "DRIVE"}:
                grouped_by_mode.setdefault(mode, []).append(row)
            else:
                blank_mode_rows.append(row)

        mode_order = ["PROD", "DRIVE", "SB"]
        merged_by_mode: dict[str, dict] = {
            mode: _merge_customer_row_group(grouped_by_mode[mode])
            for mode in mode_order
            if grouped_by_mode.get(mode)
        }

        if blank_mode_rows:
            merged_blank = _merge_customer_row_group(blank_mode_rows)
            if merged_by_mode:
                target_mode = next((mode for mode in mode_order if mode in merged_by_mode), next(iter(merged_by_mode)))
                merged_by_mode[target_mode] = _merge_customer_row_pair(merged_by_mode[target_mode], merged_blank)
                merged_by_mode[target_mode] = _normalize_customer_row(merged_by_mode[target_mode])
            else:
                deduped.append(merged_blank)

        for mode in mode_order:
            row = merged_by_mode.get(mode)
            if row:
                deduped.append(_normalize_customer_row(row))

    deduped.extend(_normalize_customer_row(row) for row in passthrough)

    # Second pass: merge weak legacy rows that have only a bare name into a stronger
    # identified row with the same canonical name, even if the legacy row has no id.
    merged_by_name: dict[str, list[dict]] = {}
    for row in deduped:
        merged_by_name.setdefault(_customer_name_dedupe_key(row.get("customer_name", "")), []).append(row)

    second_pass: list[dict] = []
    for name_key, name_rows in merged_by_name.items():
        if not name_key or len(name_rows) <= 1:
            second_pass.extend(name_rows)
            continue

        strong_rows = [
            row for row in name_rows
            if str(row.get("customer_guid") or "").strip()
            or str(row.get("customer_id") or "").strip()
            or str(row.get("source_mode") or "").strip().upper() in {"PROD", "SB", "DRIVE"}
        ]
        weak_rows = [row for row in name_rows if row not in strong_rows]

        if not strong_rows:
            second_pass.extend(name_rows)
            continue

        merged_rows = [dict(row) for row in strong_rows]
        for weak_row in weak_rows:
            target_index = max(range(len(merged_rows)), key=lambda idx: _customer_row_quality_score(merged_rows[idx]))
            merged_rows[target_index] = _normalize_customer_row(_merge_customer_row_pair(merged_rows[target_index], weak_row))

        second_pass.extend(merged_rows)

    second_pass.sort(
        key=lambda row: (
            _canonical_income_customer_name(row.get("customer_name", "")),
            str(row.get("customer_id") or ""),
            _normalize_customer_source_mode(row.get("source_mode", "")),
        )
    )
    return second_pass

SANDBOX_DEDUCTION_HEADERS = [
    "timestamp",
    "product",
    "deducted_units",
    "po_number",
    "description",
]

SANDBOX_DEDUCTION_FIELDS = [
    "timestamp",
    "product",
    "deducted_units",
    "po_number",
    "description",
]

PROJECT_MANAGER_HEADERS = [
    "חברה",
    "ח.פ",
    "כתובת אתר",
    "איש קשר",
    "תאריך הזמנה",
    "פריט",
    "טלפון איש קשר",
    "תאריכי עבר",
    "עריכה: חברה",
    "עריכה: ח.פ",
    "עריכה: כתובת אתר",
    "עריכה: איש קשר",
    "עריכה: תאריך הזמנה",
    "עריכה: פריט",
    "עריכה: טלפון איש קשר",
    "מפתח מקור",
    "עודכן לאחרונה",
]

PROJECT_MANAGER_FIELDS = [
    "company",
    "tax_id",
    "site_address",
    "contact_name",
    "order_date",
    "item",
    "contact_phone",
    "history_dates",
    "editable_company",
    "editable_tax_id",
    "editable_site_address",
    "editable_contact_name",
    "editable_order_date",
    "editable_item",
    "editable_contact_phone",
    "source_key",
    "updated_at",
]

PROJECT_MANAGER_HEADER_TO_FIELD = {
    header: field for header, field in zip(PROJECT_MANAGER_HEADERS, PROJECT_MANAGER_FIELDS)
}

PAYMENTS_HEADERS = [
    "תאריך הוצאת חשבונית",
    "שם לקוח/ספק",
    "שוטף +",
    "לתשלום או לגביה",
    "סכום",
    "מספר הזמנה",
    "תעודת משלוח",
    "חשבונית עסקה",
    "מספר חשבונית מס",
    "קבלה",
    "הערות",
    "תאריך לתשלום",
    "שולם?",
    "סביבה",
]

PAYMENTS_FIELDS = [
    "invoice_date",
    "customer_name",
    "payment_terms_days",
    "payment_direction",
    "amount",
    "po_number",
    "delivery_number",
    "proforma_invoice_number",
    "tax_invoice_number",
    "receipt_number",
    "notes",
    "due_date",
    "paid",
    "source_mode",
]

PAYMENTS_HEADER_MAP = {header: field for header, field in zip(PAYMENTS_HEADERS, PAYMENTS_FIELDS)}


def _service():
    creds = build_service_account_credentials(SCOPES)
    return build("sheets", "v4", credentials=creds)


def _fmt_amount(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _format_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""

    m = re.search(r"(\\d{2})/(\\d{2})/(\\d{4})", value)
    if m:
        d, mth, y = m.groups()
        return f"{d}/{mth}/{y}"

    m = re.search(r"(\\d{2})/(\\d{2})/(\\d{2})", value)
    if m:
        d, mth, y = m.groups()
        return f"{d}/{mth}/20{y}"

    return value


def _payment_days_only(po) -> str:
    if getattr(po, "payment_terms_days", None):
        return str(po.payment_terms_days)
    txt = (getattr(po, "payment_terms_label", "") or "").strip()
    m = re.search(r"(\\d+)", txt)
    return m.group(1) if m else ""


def _sheet_name():
    rng = settings.google_sheets_range
    return rng.split("!")[0] if "!" in rng else rng


def _payment_sheet_names(service) -> list[str]:
    metadata = _spreadsheet_metadata(service)
    names = []
    for sheet in metadata.get("sheets", []):
        title = str(sheet.get("properties", {}).get("title") or "")
        if "תשלומים והעברות" in title and "סיכום" not in title:
            names.append(title)
    def sort_key(title: str):
        if "2026" in title:
            return (2, title)
        if "2025" in title:
            return (1, title)
        return (0, title)
    return sorted(names, key=sort_key)


def _payment_current_sheet_name() -> str:
    return _sheet_name()


def _payment_sheet_bucket(title: str) -> int | None:
    raw = str(title or "").strip()
    if "2026" in raw:
        return 2026
    if "2025" in raw:
        return 2025
    return None


def _coerce_payment_date(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    for pattern in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(raw, pattern).date()
            return parsed.strftime("%d/%m/%Y")
        except Exception:
            continue
    normalized = _format_date(raw)
    if not normalized:
        return ""
    for pattern in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            parsed = datetime.strptime(normalized, pattern).date()
            return parsed.strftime("%d/%m/%Y")
        except Exception:
            continue
    return normalized


def _payment_date_sort_key(value: str):
    normalized = _coerce_payment_date(value)
    if not normalized:
        return datetime(1900, 1, 1)
    try:
        return datetime.strptime(normalized, "%d/%m/%Y")
    except Exception:
        return datetime(1900, 1, 1)


def _sheetof_due_date(issue_date_value: str, payment_terms_value: str | int | float | None) -> str:
    issue_date = _coerce_payment_date(issue_date_value)
    if not issue_date:
        return ""
    try:
        parsed_issue_date = datetime.strptime(issue_date, "%d/%m/%Y").date()
    except Exception:
        return ""
    try:
        terms_days = int(float(str(payment_terms_value or 0).strip() or 0))
    except Exception:
        terms_days = 0

    if parsed_issue_date.month == 12:
        base_date = date(parsed_issue_date.year + 1, 1, 1)
    else:
        base_date = date(parsed_issue_date.year, parsed_issue_date.month + 1, 1)

    due_date = base_date + timedelta(days=terms_days)
    if due_date.day != 1:
        if due_date.month == 12:
            due_date = date(due_date.year + 1, 1, 1)
        else:
            due_date = date(due_date.year, due_date.month + 1, 1)
    return due_date.strftime("%d/%m/%Y")


def _format_currency_display(value) -> str:
    try:
        amount = float(str(value or "").replace("₪", "").replace(",", "").strip() or 0)
    except Exception:
        amount = 0.0
    return f"₪{amount:,.2f}"


def _normalize_paid_value(value: str) -> str:
    raw = str(value or "").strip().upper()
    if raw in {"TRUE", "כן", "YES", "1"}:
        return "TRUE"
    if raw in {"FALSE", "לא", "NO", "0"}:
        return "FALSE"
    return "FALSE"


def _normalize_payment_transfer_row(row: dict | None, source_sheet: str = "") -> dict:
    row = row or {}
    normalized = {field: str(row.get(field, "") or "").strip() for field in PAYMENTS_FIELDS}
    normalized["invoice_date"] = _coerce_payment_date(normalized.get("invoice_date", "")) or datetime.now().strftime("%d/%m/%Y")
    normalized["payment_terms_days"] = re.search(r"(\d+)", normalized.get("payment_terms_days", "") or "")
    normalized["payment_terms_days"] = normalized["payment_terms_days"].group(1) if normalized["payment_terms_days"] else "0"
    normalized["payment_direction"] = (normalized.get("payment_direction") or "גביה").strip() or "גביה"
    normalized["amount"] = _format_currency_display(normalized.get("amount"))
    normalized["receipt_number"] = str(normalized.get("receipt_number", "") or "").strip()
    notes_value = str(normalized.get("notes") or "").strip()
    if (
        normalized["payment_direction"] == "גביה"
        and not normalized["receipt_number"]
        and re.fullmatch(r"\d{5,}", notes_value)
    ):
        normalized["receipt_number"] = notes_value
        normalized["notes"] = ""
    normalized_due_date = _coerce_payment_date(normalized.get("due_date", ""))
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", normalized_due_date or ""):
        normalized_due_date = ""
    normalized["due_date"] = normalized_due_date or _sheetof_due_date(
        normalized.get("invoice_date", ""),
        normalized.get("payment_terms_days", ""),
    )
    if normalized["receipt_number"] and normalized["receipt_number"] == str(normalized.get("notes") or "").strip():
        normalized["notes"] = ""
    normalized["paid"] = _normalize_paid_value(normalized.get("paid", "FALSE"))
    source_mode = str(normalized.get("source_mode") or "").strip().lower()
    normalized["source_mode"] = "SB" if source_mode in {"sb", "sandbox"} else "PROD" if source_mode in {"prod", "production"} else ""
    normalized["_sheet_title"] = source_sheet or _payment_current_sheet_name()
    return normalized


def _merge_payment_notes(notes: str, service_value: str = "") -> str:
    notes_text = str(notes or "").strip()
    service_text = str(service_value or "").strip()
    if not service_text:
        return notes_text
    if not notes_text:
        return service_text
    if service_text in notes_text:
        return notes_text
    if notes_text in service_text:
        return service_text
    return f"{notes_text} | {service_text}"


def _load_payment_paid_backup_map() -> dict[tuple[str, int], str]:
    try:
        if not _PAYMENTS_PAID_REPAIR_BACKUP_FILE.exists():
            return {}
        payload = json.loads(_PAYMENTS_PAID_REPAIR_BACKUP_FILE.read_text())
    except Exception:
        return {}
    backup_map: dict[tuple[str, int], str] = {}
    if not isinstance(payload, list):
        return backup_map
    for item in payload:
        if not isinstance(item, dict):
            continue
        sheet_title = str(item.get("sheet_title") or "").strip()
        row_number = int(item.get("row_number") or 0)
        row = item.get("row") or []
        if not sheet_title or row_number <= 0 or not isinstance(row, list) or len(row) < 14:
            continue
        backup_map[(sheet_title, row_number)] = _normalize_paid_value(row[13])
    return backup_map


def _is_payment_data_row(raw: list[str]) -> bool:
    if not raw:
        return False
    first_cell = str(raw[0] or "").strip()
    second_cell = str(raw[1] or "").strip() if len(raw) > 1 else ""
    if first_cell in {"", "L2"}:
        return False
    if second_cell in {"", "שם לקוח/ספק"}:
        return False
    return bool(re.search(r"\d{2}/\d{2}/\d{2,4}", first_cell))


def _row_to_sheet_values(row: dict) -> list[str]:
    normalized = _normalize_payment_transfer_row(row, source_sheet=str(row.get("_sheet_title") or ""))
    return [
        normalized.get("invoice_date", ""),
        normalized.get("customer_name", ""),
        normalized.get("payment_terms_days", ""),
        normalized.get("payment_direction", ""),
        normalized.get("amount", ""),
        normalized.get("po_number", ""),
        normalized.get("delivery_number", ""),
        normalized.get("proforma_invoice_number", ""),
        normalized.get("tax_invoice_number", ""),
        normalized.get("receipt_number", ""),
        normalized.get("notes", ""),
        normalized.get("due_date", ""),
        normalized.get("paid", "FALSE"),
        normalized.get("source_mode", ""),
    ]


def _load_payments_transfer_disk_cache() -> dict | None:
    global _PAYMENTS_TRANSFER_STATE_CACHE, _PAYMENTS_TRANSFER_STATE_CACHE_TS
    try:
        if not _PAYMENTS_TRANSFER_CACHE_FILE.exists():
            return None
        payload = json.loads(_PAYMENTS_TRANSFER_CACHE_FILE.read_text())
        if not isinstance(payload, dict):
            return None
        _PAYMENTS_TRANSFER_STATE_CACHE = copy.deepcopy(payload)
        _PAYMENTS_TRANSFER_STATE_CACHE_TS = time.time()
        return copy.deepcopy(payload)
    except Exception:
        return None


def _save_payments_transfer_disk_cache(payload: dict) -> None:
    try:
        _PAYMENTS_TRANSFER_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _PAYMENTS_TRANSFER_CACHE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    except Exception:
        pass


def _load_payments_transfer_supabase_cache() -> dict | None:
    if not _supabase_enabled_for("payments_transfer_state"):
        return None
    try:
        rows = supabase_store.fetch_domain_rows("payments_transfer_state")
    except Exception:
        return None
    if not rows:
        return None
    payload = rows[0]
    if not isinstance(payload, dict):
        return None
    normalized = copy.deepcopy(payload)
    normalized["id"] = str(normalized.get("id") or "current").strip() or "current"
    return normalized


def _save_payments_transfer_supabase_cache(payload: dict) -> None:
    if not _supabase_enabled_for("payments_transfer_state"):
        return
    try:
        normalized = copy.deepcopy(payload)
        normalized["id"] = str(normalized.get("id") or "current").strip() or "current"
        supabase_store.replace_domain_rows("payments_transfer_state", [normalized])
    except Exception:
        pass


def _cache_payments_transfer_state(payload: dict) -> dict:
    global _PAYMENTS_TRANSFER_STATE_CACHE, _PAYMENTS_TRANSFER_STATE_CACHE_TS
    _PAYMENTS_TRANSFER_STATE_CACHE = copy.deepcopy(payload)
    _PAYMENTS_TRANSFER_STATE_CACHE_TS = time.time()
    _save_payments_transfer_supabase_cache(_PAYMENTS_TRANSFER_STATE_CACHE)
    _save_payments_transfer_disk_cache(_PAYMENTS_TRANSFER_STATE_CACHE)
    return copy.deepcopy(_PAYMENTS_TRANSFER_STATE_CACHE)


def _get_cached_payments_transfer_state() -> dict | None:
    global _PAYMENTS_TRANSFER_STATE_CACHE, _PAYMENTS_TRANSFER_STATE_CACHE_TS
    if _PAYMENTS_TRANSFER_STATE_CACHE is not None:
        return copy.deepcopy(_PAYMENTS_TRANSFER_STATE_CACHE)
    supabase_cached = _load_payments_transfer_supabase_cache()
    if supabase_cached:
        _PAYMENTS_TRANSFER_STATE_CACHE = copy.deepcopy(supabase_cached)
        _PAYMENTS_TRANSFER_STATE_CACHE_TS = time.time()
        _save_payments_transfer_disk_cache(supabase_cached)
        return copy.deepcopy(supabase_cached)
    return _load_payments_transfer_disk_cache()


def _payments_transfer_cache_is_fresh() -> bool:
    return (
        _PAYMENTS_TRANSFER_STATE_CACHE is not None
        and (time.time() - _PAYMENTS_TRANSFER_STATE_CACHE_TS) <= _PAYMENTS_TRANSFER_CACHE_TTL_SECONDS
    )


def warm_local_caches_from_disk() -> dict[str, int]:
    global _CUSTOMER_ROWS_CACHE, _CUSTOMER_ROWS_CACHE_TS, _INACTIVE_CUSTOMER_ROWS_CACHE, _INACTIVE_CUSTOMER_ROWS_CACHE_TS
    global _ORDER_HISTORY_ROWS_CACHE, _ORDER_HISTORY_ROWS_CACHE_TS, _QUOTE_HISTORY_ROWS_CACHE, _QUOTE_HISTORY_ROWS_CACHE_TS
    global _INSTALLATION_CASE_ROWS_CACHE, _INSTALLATION_CASE_ROWS_CACHE_TS, _INSTALLATION_VISIT_ROWS_CACHE, _INSTALLATION_VISIT_ROWS_CACHE_TS
    global _PAZOMAT_ROWS_CACHE, _PAZOMAT_ROWS_CACHE_TS, _SIBUS_ROWS_CACHE, _SIBUS_ROWS_CACHE_TS
    global _WORKING_ORDER_ROWS_CACHE, _WORKING_ORDER_ROWS_CACHE_TS
    global _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE, _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE_TS
    global _INVENTORY_PURCHASE_ORDER_ROWS_CACHE, _INVENTORY_PURCHASE_ORDER_ROWS_CACHE_TS
    global _PRICING_ITEM_ROWS_CACHE, _PRICING_ITEM_ROWS_CACHE_TS, _PRICING_COMPONENT_ROWS_CACHE, _PRICING_COMPONENT_ROWS_CACHE_TS

    warmed: dict[str, int] = {}

    payments_payload = _load_payments_transfer_disk_cache()
    if payments_payload:
        all_rows = payments_payload.get("all_rows") or []
        warmed["payments_transfer"] = len(all_rows) if isinstance(all_rows, list) else 0

    for kind in (
        "finance_invoices",
        "finance_settings",
        "finance_customer_withholdings",
        "finance_bank_movements",
        "pipeline",
        "work_managers",
        "construction_companies",
        "notes",
        "reminders",
        "history",
    ):
        rows = _load_marketing_disk_cache(kind)
        if rows:
            _set_marketing_cache(kind, rows)
            warmed[kind] = len(rows)

    active_customers = _load_customers_disk_cache("active")
    if active_customers:
        _CUSTOMER_ROWS_CACHE = [dict(row) for row in active_customers]
        _CUSTOMER_ROWS_CACHE_TS = time.time()
        warmed["customers_active"] = len(active_customers)

    inactive_customers = _load_customers_disk_cache("inactive")
    if inactive_customers:
        _INACTIVE_CUSTOMER_ROWS_CACHE = [dict(row) for row in inactive_customers]
        _INACTIVE_CUSTOMER_ROWS_CACHE_TS = time.time()
        warmed["customers_inactive"] = len(inactive_customers)

    order_history_rows = _load_order_history_disk_cache()
    if order_history_rows:
        _ORDER_HISTORY_ROWS_CACHE = [dict(row) for row in order_history_rows]
        _ORDER_HISTORY_ROWS_CACHE_TS = time.time()
        warmed["order_history"] = len(order_history_rows)

    quote_history_rows = _load_quote_history_disk_cache()
    if quote_history_rows:
        _QUOTE_HISTORY_ROWS_CACHE = [dict(row) for row in quote_history_rows]
        _QUOTE_HISTORY_ROWS_CACHE_TS = time.time()
        warmed["quote_history"] = len(quote_history_rows)

    installation_case_rows = _load_installation_cases_disk_cache()
    if installation_case_rows:
        _INSTALLATION_CASE_ROWS_CACHE = [dict(row) for row in installation_case_rows]
        _INSTALLATION_CASE_ROWS_CACHE_TS = time.time()
        warmed["installation_cases"] = len(installation_case_rows)

    installation_visit_rows = _load_installation_visits_disk_cache()
    if installation_visit_rows:
        _INSTALLATION_VISIT_ROWS_CACHE = [dict(row) for row in installation_visit_rows]
        _INSTALLATION_VISIT_ROWS_CACHE_TS = time.time()
        warmed["installation_visits"] = len(installation_visit_rows)

    pazomat_rows = _load_pazomat_disk_cache()
    if pazomat_rows:
        _PAZOMAT_ROWS_CACHE = [dict(row) for row in pazomat_rows]
        _PAZOMAT_ROWS_CACHE_TS = time.time()
        warmed["pazomat"] = len(pazomat_rows)

    sibus_rows = _load_sibus_disk_cache()
    if sibus_rows:
        _SIBUS_ROWS_CACHE = [dict(row) for row in sibus_rows]
        _SIBUS_ROWS_CACHE_TS = time.time()
        warmed["sibus"] = len(sibus_rows)

    working_order_rows = _load_working_order_disk_cache()
    if working_order_rows:
        _WORKING_ORDER_ROWS_CACHE = [dict(row) for row in working_order_rows]
        _WORKING_ORDER_ROWS_CACHE_TS = time.time()
        warmed["working_orders"] = len(working_order_rows)

    supplier_delivery_rows = _load_supplier_delivery_note_disk_cache()
    if supplier_delivery_rows:
        _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE = [dict(row) for row in supplier_delivery_rows]
        _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE_TS = time.time()
        warmed["supplier_delivery_notes"] = len(supplier_delivery_rows)

    inventory_po_rows = _load_inventory_purchase_order_disk_cache()
    if inventory_po_rows:
        _INVENTORY_PURCHASE_ORDER_ROWS_CACHE = [dict(row) for row in inventory_po_rows]
        _INVENTORY_PURCHASE_ORDER_ROWS_CACHE_TS = time.time()
        warmed["inventory_purchase_orders"] = len(inventory_po_rows)

    pricing_item_rows = _load_pricing_items_disk_cache()
    if pricing_item_rows:
        _PRICING_ITEM_ROWS_CACHE = [dict(row) for row in pricing_item_rows]
        _PRICING_ITEM_ROWS_CACHE_TS = time.time()
        warmed["pricing_items"] = len(pricing_item_rows)

    pricing_component_rows = _load_pricing_components_disk_cache()
    if pricing_component_rows:
        _PRICING_COMPONENT_ROWS_CACHE = [dict(row) for row in pricing_component_rows]
        _PRICING_COMPONENT_ROWS_CACHE_TS = time.time()
        warmed["pricing_components"] = len(pricing_component_rows)

    project_manager_rows = _load_project_managers_disk_cache()
    if project_manager_rows:
        warmed["project_managers"] = len(project_manager_rows)

    delivery_confirmation_rows = _load_delivery_disk_cache("confirmations")
    if delivery_confirmation_rows:
        warmed["delivery_confirmations"] = len(delivery_confirmation_rows)

    delivery_contact_rows = _load_delivery_disk_cache("contacts")
    if delivery_contact_rows:
        warmed["delivery_contacts"] = len(delivery_contact_rows)

    return warmed


def _payment_row_cache_identity(row: dict) -> tuple[str, int]:
    return (
        str(row.get("_sheet_title") or "").strip(),
        int(row.get("_sheet_row") or 0),
    )


def _payment_row_cache_business_key(row: dict) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "").strip() for field in PAYMENTS_FIELDS)


def _delivery_confirmation_source_mode_map() -> dict[tuple[str, str, str], str]:
    rows = _DELIVERY_CONFIRMATION_ROWS_CACHE or _load_delivery_disk_cache("confirmations")
    mapping: dict[tuple[str, str, str], str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        source_mode = str(row.get("source_mode") or "").strip().upper()
        if not source_mode:
            continue
        key = (
            _canonicalize_project_manager_company(row.get("company", "")),
            str(row.get("po_number", "") or "").strip(),
            str(row.get("tax_invoice_number", "") or "").strip(),
        )
        mapping[key] = source_mode
    return mapping


def _ensure_payment_sheet_schema(service, sheet_title: str) -> None:
    now_ts = time.time()
    if (now_ts - _PAYMENT_SCHEMA_ENSURED_AT.get(sheet_title, 0.0)) < _PAYMENT_SCHEMA_CACHE_TTL_SECONDS:
        return

    def _clear_legacy_column_o():
        service.spreadsheets().values().clear(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"'{sheet_title}'!O:O",
            body={},
        ).execute()

    def _ensure_paid_checkbox():
        sheet_id = _sheet_id_by_title(service, sheet_title)
        if sheet_id is None:
            return
        service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body={
                "requests": [
                    {
                        "setDataValidation": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": 1,
                                "startColumnIndex": 12,
                                "endColumnIndex": 13,
                            },
                            "rule": {
                                "condition": {"type": "BOOLEAN"},
                                "showCustomUi": True,
                                "strict": False,
                            },
                        }
                    }
                ]
            },
        ).execute()

    def _ensure_paid_conditional_formatting():
        sheet_id = _sheet_id_by_title(service, sheet_title)
        if sheet_id is None:
            return
        metadata = service.spreadsheets().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            fields="sheets(properties(sheetId,title),conditionalFormats)",
        ).execute()
        target_sheet = next(
            (sheet for sheet in metadata.get("sheets", []) if sheet.get("properties", {}).get("sheetId") == sheet_id),
            None,
        )
        if not target_sheet:
            return
        rules = target_sheet.get("conditionalFormats", [])
        delete_indexes: list[int] = []
        for index, rule in enumerate(rules):
            boolean_rule = rule.get("booleanRule", {})
            condition = boolean_rule.get("condition", {})
            values = condition.get("values", [])
            formula = ""
            if values:
                formula = str(values[0].get("userEnteredValue") or "").strip().upper()
            if "TODAY()" in formula or "$N" in formula or "$M" in formula or "$L" in formula:
                delete_indexes.append(index)
        requests: list[dict] = []
        for index in sorted(delete_indexes, reverse=True):
            requests.append(
                {
                    "deleteConditionalFormatRule": {
                        "sheetId": sheet_id,
                        "index": index,
                    }
                }
            )
        requests.extend(
            [
                {
                    "addConditionalFormatRule": {
                        "index": 0,
                        "rule": {
                            "ranges": [
                                {
                                    "sheetId": sheet_id,
                                    "startRowIndex": 1,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": 14,
                                }
                            ],
                            "booleanRule": {
                                "condition": {
                                    "type": "CUSTOM_FORMULA",
                                    "values": [{"userEnteredValue": "=$M2=TRUE"}],
                                },
                                "format": {
                                    "backgroundColor": {"red": 0.7176471, "green": 0.88235295, "blue": 0.8039216},
                                    "backgroundColorStyle": {
                                        "rgbColor": {"red": 0.7176471, "green": 0.88235295, "blue": 0.8039216}
                                    },
                                },
                            },
                        },
                    }
                },
                {
                    "addConditionalFormatRule": {
                        "index": 1,
                        "rule": {
                            "ranges": [
                                {
                                    "sheetId": sheet_id,
                                    "startRowIndex": 1,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": 14,
                                }
                            ],
                            "booleanRule": {
                                "condition": {
                                    "type": "CUSTOM_FORMULA",
                                    "values": [{"userEnteredValue": '=AND($L2<>"",$L2<TODAY(),$M2=FALSE)'}],
                                },
                                "format": {
                                    "backgroundColor": {"red": 0.8784314, "green": 0.4, "blue": 0.4},
                                    "backgroundColorStyle": {
                                        "rgbColor": {"red": 0.8784314, "green": 0.4, "blue": 0.4}
                                    },
                                },
                            },
                        },
                    }
                },
            ]
        )
        if requests:
            service.spreadsheets().batchUpdate(
                spreadsheetId=settings.google_sheets_spreadsheet_id,
                body={"requests": requests},
            ).execute()

    backup_paid_map = _load_payment_paid_backup_map()

    def _repair_misplaced_due_date_rows(existing_values: list[list[str]]) -> bool:
        updates: list[dict] = []
        changed = False
        for idx, raw in enumerate(existing_values[1:], start=2):
            padded = raw + [""] * max(0, 13 - len(raw))
            due_candidate = str(padded[11] or "").strip()
            paid_candidate = str(padded[12] or "").strip()
            if due_candidate.lower() not in {"automation", "אוטומציה"}:
                continue
            if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", paid_candidate):
                continue
            padded[11] = paid_candidate
            padded[12] = "FALSE"
            updates.append(
                {
                    "range": f"'{sheet_title}'!A{idx}:M{idx}",
                    "values": [padded[:13]],
                }
            )
            changed = True
        if updates:
            _batch_update_payment_rows(service, updates)
            _ensure_paid_checkbox()
        return changed

    def _repair_shifted_due_and_paid(existing_values: list[list[str]]) -> bool:
        updates: list[dict] = []
        changed = False
        for idx, raw in enumerate(existing_values[1:], start=2):
            padded = raw + [""] * max(0, 15 - len(raw))
            payment_direction = str(padded[3] or "").strip()
            due_candidate = str(padded[11] or "").strip()
            paid_candidate = str(padded[12] or "").strip()
            legacy_paid_candidate = str(padded[13] or "").strip()
            if due_candidate:
                continue
            if not re.fullmatch(r"\d{2}/\d{2}/\d{4}", paid_candidate):
                continue
            restored_paid = ""
            if legacy_paid_candidate.upper() in {"TRUE", "FALSE", "כן", "לא", "YES", "NO", "1", "0"}:
                restored_paid = _normalize_paid_value(legacy_paid_candidate)
            else:
                # Never trust the old backup blindly for supplier payments: those
                # rows have no external receipt source, and restoring them from an
                # old shifted schema can incorrectly mark unpaid rows as paid.
                if payment_direction == "תשלום":
                    restored_paid = "FALSE"
                else:
                    restored_paid = backup_paid_map.get((sheet_title, idx), "FALSE")
            padded[11] = paid_candidate
            padded[12] = restored_paid
            updates.append(
                {
                    "range": f"'{sheet_title}'!A{idx}:M{idx}",
                    "values": [padded[:13]],
                }
            )
            changed = True
        if updates:
            _batch_update_payment_rows(service, updates)
            _ensure_paid_checkbox()
        return changed

    def _repair_invalid_due_dates_and_duplicate_notes(existing_values: list[list[str]]) -> bool:
        updates: list[dict] = []
        changed = False
        for idx, raw in enumerate(existing_values[1:], start=2):
            padded = raw + [""] * max(0, 14 - len(raw))
            payment_direction = str(padded[3] or "").strip()
            receipt_number = str(padded[9] or "").strip()
            notes_value = str(padded[10] or "").strip()
            due_candidate = str(padded[11] or "").strip()
            paid_candidate = str(padded[12] or "").strip()
            row_changed = False

            if payment_direction == "גביה" and not receipt_number and re.fullmatch(r"\d{5,}", notes_value):
                padded[9] = notes_value
                padded[10] = ""
                receipt_number = notes_value
                notes_value = ""
                row_changed = True

            if receipt_number and notes_value and receipt_number == notes_value:
                padded[10] = ""
                row_changed = True

            due_is_valid = bool(re.fullmatch(r"\d{2}/\d{2}/\d{4}", _coerce_payment_date(due_candidate or "")))
            paid_is_date = bool(re.fullmatch(r"\d{2}/\d{2}/\d{4}", _coerce_payment_date(paid_candidate or "")))
            if due_candidate and not due_is_valid and paid_is_date:
                padded[11] = _coerce_payment_date(paid_candidate)
                padded[12] = "FALSE"
                row_changed = True

            if row_changed:
                updates.append(
                    {
                        "range": f"'{sheet_title}'!A{idx}:N{idx}",
                        "values": [padded[:14]],
                    }
                )
                changed = True
        if updates:
            _batch_update_payment_rows(service, updates)
            _ensure_paid_checkbox()
        return changed

    values = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"'{sheet_title}'!A:O",
    ).execute().get("values", [])

    if not values:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"'{sheet_title}'!A1:N1",
            valueInputOption="USER_ENTERED",
            body={"values": [PAYMENTS_HEADERS]},
        ).execute()
        _ensure_paid_checkbox()
        _ensure_paid_conditional_formatting()
        _PAYMENT_SCHEMA_ENSURED_AT[sheet_title] = time.time()
        return

    header = values[0] + [""] * max(0, len(PAYMENTS_HEADERS) - len(values[0]))
    if header[:len(PAYMENTS_HEADERS)] == PAYMENTS_HEADERS:
        _repair_shifted_due_and_paid(values)
        refreshed_values = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"'{sheet_title}'!A:O",
        ).execute().get("values", [])
        _repair_invalid_due_dates_and_duplicate_notes(refreshed_values)
        _ensure_paid_checkbox()
        _ensure_paid_conditional_formatting()
        refreshed_values = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"'{sheet_title}'!A:O",
        ).execute().get("values", [])
        _repair_misplaced_due_date_rows(refreshed_values)
        _clear_legacy_column_o()
        _PAYMENT_SCHEMA_ENSURED_AT[sheet_title] = time.time()
        return

    migrated_rows = [PAYMENTS_HEADERS]
    for raw in values[1:]:
        if len(raw) >= 14:
            padded = raw + [""] * max(0, 14 - len(raw))
            migrated_rows.append([
                padded[0],
                padded[1],
                padded[2],
                padded[3],
                padded[4],
                padded[5],
                padded[6],
                padded[7],
                padded[8],
                padded[9],
                _merge_payment_notes(padded[11], padded[10]),
                padded[12],
                padded[13],
                "",
            ])
        else:
            padded = raw + [""] * max(0, 14 - len(raw))
            if len(raw) == 13:
                migrated_rows.append([
                    padded[0],
                    padded[1],
                    padded[2],
                    padded[3],
                    padded[4],
                    padded[5],
                    padded[6],
                    padded[7],
                    padded[8],
                    "",
                    _merge_payment_notes(padded[10], padded[9]),
                    padded[11],
                    padded[12],
                    "",
                ])
            else:
                migrated_rows.append(padded[:len(PAYMENTS_HEADERS)])

    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"'{sheet_title}'!A1:N{len(migrated_rows)}",
        valueInputOption="USER_ENTERED",
        body={"values": migrated_rows},
    ).execute()
    _clear_legacy_column_o()
    _ensure_paid_checkbox()
    _ensure_paid_conditional_formatting()
    _repair_invalid_due_dates_and_duplicate_notes(migrated_rows)
    _repair_misplaced_due_date_rows(migrated_rows)
    _PAYMENT_SCHEMA_ENSURED_AT[sheet_title] = time.time()


def _batch_update_payment_rows(service, updates: list[dict]) -> None:
    if not updates:
        return
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": updates,
        },
    ).execute()


def _next_empty_row(service, sheet_name=None):
    sheet = sheet_name or _sheet_name()
    result = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{sheet}!A:A",
    ).execute()

    values = result.get("values", [])
    return len(values) + 1


def append_payment_row(po, delivery_doc, invoice_doc, source_mode: str = ""):
    service = _service()
    sheet = _payment_current_sheet_name()
    _ensure_payment_sheet_schema(service, sheet)
    row_data = _normalize_payment_transfer_row(
        {
            "invoice_date": _format_date(po.po_date) or datetime.now().strftime("%d/%m/%Y"),
            "customer_name": po.customer_name,
            "payment_terms_days": _payment_days_only(po),
            "payment_direction": "גביה",
            "amount": po.total,
            "po_number": po.po_number or "",
            "delivery_number": getattr(delivery_doc, "number", ""),
            "proforma_invoice_number": "",
            "tax_invoice_number": getattr(invoice_doc, "number", ""),
            "notes": "אוטומציה",
            "due_date": "",
            "paid": "FALSE",
            "source_mode": source_mode,
        },
        source_sheet=sheet,
    )
    existing_rows = list((load_payment_transfer_rows() or {}).get("all_rows") or [])
    source_mode_key = str(source_mode or "").strip().upper()
    target_row = next(
        (
            row
            for row in existing_rows
            if str(row.get("payment_direction") or "").strip() == "גביה"
            and _canonical_income_customer_name(row.get("customer_name", "")) == _canonical_income_customer_name(po.customer_name)
            and str(row.get("po_number") or "").strip() == str(po.po_number or "").strip()
            and str(row.get("source_mode") or "").strip().upper() == source_mode_key
        ),
        None,
    )
    row = _row_to_sheet_values(row_data)

    if target_row and str(target_row.get("_sheet_title") or "").strip() and int(target_row.get("_sheet_row") or 0) > 0:
        row_num = int(target_row.get("_sheet_row") or 0)
        target_sheet = str(target_row.get("_sheet_title") or "").strip()
        result = (
            service.spreadsheets()
            .values()
            .update(
                spreadsheetId=settings.google_sheets_spreadsheet_id,
                range=f"{target_sheet}!A{row_num}:N{row_num}",
                valueInputOption="USER_ENTERED",
                body={"values": [row]},
            )
            .execute()
        )
        row_data["_sheet_row"] = row_num
        row_data["_sheet_title"] = target_sheet
        _replace_payment_transfer_cache_row(row_data)
        return {
            "target_row": row_num,
            "target_sheet": target_sheet,
            "written_values": row_data,
            "api_result": result,
            "updated_existing": True,
        }

    row_num = _next_empty_row(service, sheet)
    result = (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{sheet}!A{row_num}:N{row_num}",
            valueInputOption="USER_ENTERED",
            body={"values": [row]},
        )
        .execute()
    )

    print("✅ SHEETS: append success")
    row_data["_sheet_row"] = row_num
    row_data["_sheet_title"] = sheet
    _replace_payment_transfer_cache_row(row_data)

    return {
        "target_row": row_num,
        "target_sheet": sheet,
        "written_values": row_data,
        "api_result": result,
        "updated_existing": False,
    }


def _build_payment_transfer_state(
    all_rows: list[dict],
    *,
    sheet_names: list[str] | None = None,
    current_sheet: str | None = None,
) -> dict:
    normalized_rows = [dict(row) for row in (all_rows or [])]
    comparable_fields = [field for field in PAYMENTS_FIELDS if field not in {"paid", "receipt_number"}]
    deduped_rows: dict[tuple, dict] = {}
    for row in normalized_rows:
        key = tuple(str(row.get(field) or "").strip() for field in comparable_fields)
        existing = deduped_rows.get(key)
        if not existing:
            deduped_rows[key] = row
            continue

        existing_bucket = _payment_sheet_bucket(str(existing.get("_sheet_title") or "")) or 0
        row_bucket = _payment_sheet_bucket(str(row.get("_sheet_title") or "")) or 0
        existing_paid = str(existing.get("paid") or "").strip().upper() == "TRUE"
        row_paid = str(row.get("paid") or "").strip().upper() == "TRUE"

        if row_bucket > existing_bucket:
            primary = dict(row)
            secondary = existing
        elif existing_bucket > row_bucket:
            primary = dict(existing)
            secondary = row
        elif row_paid and not existing_paid:
            primary = dict(row)
            secondary = existing
        else:
            primary = dict(existing)
            secondary = row

        merged = dict(primary)
        for field in comparable_fields:
            if not str(merged.get(field) or "").strip() and str(secondary.get(field) or "").strip():
                merged[field] = secondary.get(field)

        if row_bucket == existing_bucket:
            if not str(merged.get("receipt_number") or "").strip() and str(secondary.get("receipt_number") or "").strip():
                merged["receipt_number"] = secondary.get("receipt_number")
            merged["paid"] = "TRUE" if (existing_paid or row_paid) else "FALSE"
        else:
            merged["receipt_number"] = str(primary.get("receipt_number") or "").strip()
            merged["paid"] = _normalize_paid_value(primary.get("paid", "FALSE"))

        if not merged.get("_sheet_title") and secondary.get("_sheet_title"):
            merged["_sheet_title"] = secondary.get("_sheet_title")
        if not merged.get("_sheet_row") and secondary.get("_sheet_row"):
            merged["_sheet_row"] = secondary.get("_sheet_row")
        deduped_rows[key] = merged

    deduped_all_rows = list(deduped_rows.values())
    deduped_all_rows.sort(
        key=lambda row: (
            _payment_date_sort_key(row.get("invoice_date", "")),
            row.get("customer_name", ""),
        ),
        reverse=True,
    )

    payments_2026_collection: list[dict] = []
    payments_2026_payment: list[dict] = []
    threshold_date = date(2026, 1, 1)
    minimum_invoice_date = date(2025, 1, 1)
    today = date.today()

    for row in deduped_all_rows:
        row_year = _payment_sheet_bucket(str(row.get("_sheet_title") or ""))
        if row_year not in {2025, 2026}:
            continue

        invoice_date_value = _coerce_payment_date(str(row.get("invoice_date") or ""))
        due_date_value = _coerce_payment_date(str(row.get("due_date") or ""))
        try:
            invoice_date = datetime.strptime(invoice_date_value, "%d/%m/%Y").date() if invoice_date_value else None
        except ValueError:
            invoice_date = None
        try:
            due_date = datetime.strptime(due_date_value, "%d/%m/%Y").date() if due_date_value else None
        except ValueError:
            due_date = None

        if invoice_date and invoice_date < minimum_invoice_date:
            continue

        paid = str(row.get("paid") or "").strip().upper() == "TRUE"
        overdue_unpaid = (not paid) and bool(due_date and due_date < today)
        include_row = False

        if invoice_date and invoice_date >= threshold_date:
            include_row = True
        elif due_date and due_date >= threshold_date:
            include_row = True
        elif not paid or overdue_unpaid:
            include_row = True

        if not include_row:
            continue

        payment_direction = str(row.get("payment_direction") or "").strip()
        if payment_direction == "תשלום":
            payments_2026_payment.append(row)
        else:
            payments_2026_collection.append(row)

    return {
        "headers": PAYMENTS_HEADERS,
        "recent_rows": [],
        "historical_rows": [],
        "all_rows": deduped_all_rows,
        "payments_2026_collection": payments_2026_collection,
        "payments_2026_payment": payments_2026_payment,
        "payments_2025_collection": [],
        "payments_2025_payment": [],
        "sheet_names": list(sheet_names or []),
        "current_sheet": current_sheet or _payment_current_sheet_name(),
    }


def _replace_payment_transfer_cache_row(row: dict) -> None:
    cached = _get_cached_payments_transfer_state()
    if not cached:
        return
    normalized = _normalize_payment_transfer_row(row, source_sheet=str(row.get("_sheet_title") or ""))
    if row.get("_sheet_row"):
        normalized["_sheet_row"] = int(row.get("_sheet_row") or 0)
    all_rows = [dict(item) for item in (cached.get("all_rows") or [])]
    target_identity = _payment_row_cache_identity(normalized)
    target_business_key = _payment_row_cache_business_key(normalized)
    replaced = False
    for index, existing in enumerate(all_rows):
        if target_identity[0] and target_identity[1] > 0 and _payment_row_cache_identity(existing) == target_identity:
            all_rows[index] = normalized
            replaced = True
            break
        if _payment_row_cache_business_key(existing) == target_business_key:
            all_rows[index] = normalized
            replaced = True
            break
    if not replaced:
        all_rows.append(normalized)
    _cache_payments_transfer_state(
        _build_payment_transfer_state(
            all_rows,
            sheet_names=cached.get("sheet_names") or [],
            current_sheet=str(cached.get("current_sheet") or _payment_current_sheet_name()),
        )
    )


def _update_payment_transfer_cache_by_sheet_row(sheet_title: str, row_number: int, updater) -> None:
    cached = _get_cached_payments_transfer_state()
    if not cached:
        return
    all_rows = [dict(item) for item in (cached.get("all_rows") or [])]
    changed = False
    for row in all_rows:
        if str(row.get("_sheet_title") or "").strip() != sheet_title or int(row.get("_sheet_row") or 0) != int(row_number):
            continue
        updater(row)
        changed = True
        break
    if not changed:
        return
    _cache_payments_transfer_state(
        _build_payment_transfer_state(
            all_rows,
            sheet_names=cached.get("sheet_names") or [],
            current_sheet=str(cached.get("current_sheet") or _payment_current_sheet_name()),
        )
    )


def _delete_payment_transfer_cache_rows(target_row: dict, deleted_sheets: list[str] | None = None) -> None:
    cached = _get_cached_payments_transfer_state()
    if not cached:
        return
    all_rows = [dict(item) for item in (cached.get("all_rows") or [])]
    target_identity = _payment_row_cache_identity(target_row)
    target_business_key = _payment_row_cache_business_key(target_row)
    deleted_sheet_set = {str(title or "").strip() for title in (deleted_sheets or [])}
    kept_rows: list[dict] = []
    for row in all_rows:
        same_identity = (
            target_identity[0]
            and target_identity[1] > 0
            and _payment_row_cache_identity(row) == target_identity
        )
        same_business_key = _payment_row_cache_business_key(row) == target_business_key
        deleted_sheet_match = str(row.get("_sheet_title") or "").strip() in deleted_sheet_set if deleted_sheet_set else False
        if same_identity or (same_business_key and (not deleted_sheet_set or deleted_sheet_match)):
            continue
        kept_rows.append(row)
    _cache_payments_transfer_state(
        _build_payment_transfer_state(
            kept_rows,
            sheet_names=cached.get("sheet_names") or [],
            current_sheet=str(cached.get("current_sheet") or _payment_current_sheet_name()),
        )
    )


def repair_all_payment_transfer_sheets() -> None:
    service = _service()
    for title in _payment_sheet_names(service):
        _ensure_payment_sheet_schema(service, title)


def load_payment_transfer_rows(
    force_refresh: bool = False,
    repair_schema: bool = False,
    enrich_source_mode: bool = False,
) -> dict:
    cached = _get_cached_payments_transfer_state()
    if not force_refresh and _payments_transfer_cache_is_fresh() and cached:
        return cached

    service = _service()
    try:
        sheet_names = _payment_sheet_names(service)
        if repair_schema:
            for title in sheet_names:
                _ensure_payment_sheet_schema(service, title)
        all_rows: list[dict] = []
        ranges = [f"'{title}'!A:N" for title in sheet_names]

        value_ranges = []
        if ranges:
            batch_result = service.spreadsheets().values().batchGet(
                spreadsheetId=settings.google_sheets_spreadsheet_id,
                ranges=ranges,
            ).execute()
            value_ranges = batch_result.get("valueRanges", [])
        values_by_title: dict[str, list[list[str]]] = {}
        for value_range in value_ranges:
            range_name = str(value_range.get("range") or "")
            m = re.match(r"^'?(.*?)'?!", range_name)
            title = m.group(1) if m else ""
            if title:
                values_by_title[title] = value_range.get("values", []) or []

        for title in sheet_names:
            values = values_by_title.get(title, [])
            for row_index, raw in enumerate(values, start=1):
                if not _is_payment_data_row(raw):
                    continue
                all_rows.append(_payment_row_from_raw(raw, title, row_index))

        if enrich_source_mode:
            source_mode_map = _delivery_confirmation_source_mode_map()
            source_mode_updates: list[dict] = []
            for row in all_rows:
                if str(row.get("source_mode") or "").strip():
                    continue
                key = (
                    _canonicalize_project_manager_company(row.get("customer_name", "")),
                    str(row.get("po_number", "") or "").strip(),
                    str(row.get("tax_invoice_number", "") or "").strip(),
                )
                source_mode = source_mode_map.get(key, "")
                if not source_mode:
                    continue
                row["source_mode"] = source_mode
                sheet_title = str(row.get("_sheet_title") or "").strip()
                row_number = int(row.get("_sheet_row") or 0)
                if sheet_title and row_number > 0:
                    source_mode_updates.append(
                        {
                            "range": f"'{sheet_title}'!N{row_number}",
                            "values": [[source_mode]],
                        }
                    )
            if source_mode_updates:
                _batch_update_payment_rows(service, source_mode_updates)

        payload = _build_payment_transfer_state(
            all_rows,
            sheet_names=sheet_names,
            current_sheet=_payment_current_sheet_name(),
        )
        return _cache_payments_transfer_state(payload)
    except Exception as exc:
        if _is_rate_limit_error(exc) and cached:
            return cached
        raise


def append_manual_payment_transfer_row(row: dict) -> dict:
    service = _service()
    sheet = _payment_current_sheet_name()
    _ensure_payment_sheet_schema(service, sheet)
    row_num = _next_empty_row(service, sheet)
    normalized = _normalize_payment_transfer_row(row, source_sheet=sheet)
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{sheet}!A{row_num}:N{row_num}",
        valueInputOption="USER_ENTERED",
        body={"values": [_row_to_sheet_values(normalized)]},
    ).execute()
    normalized["_sheet_row"] = row_num
    _replace_payment_transfer_cache_row(normalized)
    return {
        "target_row": row_num,
        "sheet": sheet,
        "written_values": normalized,
    }


def update_payment_transfer_paid(sheet_title: str, row_number: int, paid: str | bool) -> dict:
    service = _service()
    _ensure_payment_sheet_schema(service, sheet_title)
    normalized_paid = _normalize_paid_value(str(paid))
    if normalized_paid == "TRUE":
        values = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"'{sheet_title}'!A{int(row_number)}:N{int(row_number)}",
        ).execute().get("values", [])
        current_row = _payment_row_from_raw(values[0], sheet_title, int(row_number)) if values else None
        payment_direction = str((current_row or {}).get("payment_direction") or "").strip()
        receipt_number = str((current_row or {}).get("receipt_number") or "").strip()
        if payment_direction == "גביה" and not receipt_number:
            raise ValueError("כדי לסמן שורת גבייה כשולמה צריך להפיק קודם קבלה מתוך המודאל.")
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"'{sheet_title}'!M{int(row_number)}",
        valueInputOption="USER_ENTERED",
        body={"values": [[normalized_paid]]},
    ).execute()
    _update_payment_transfer_cache_by_sheet_row(
        sheet_title,
        int(row_number),
        lambda row: row.__setitem__("paid", normalized_paid),
    )
    return {
        "sheet": sheet_title,
        "row": int(row_number),
        "paid": normalized_paid,
    }


def update_payment_transfer_row(sheet_title: str, row_number: int, row: dict) -> dict:
    service = _service()
    _ensure_payment_sheet_schema(service, sheet_title)
    normalized = _normalize_payment_transfer_row(
        {
            **row,
            "_sheet_title": sheet_title,
            "_sheet_row": int(row_number),
        },
        source_sheet=sheet_title,
    )
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"'{sheet_title}'!A{int(row_number)}:N{int(row_number)}",
        valueInputOption="USER_ENTERED",
        body={"values": [_row_to_sheet_values(normalized)]},
    ).execute()
    normalized["_sheet_row"] = int(row_number)
    _replace_payment_transfer_cache_row(normalized)
    return {
        "sheet": sheet_title,
        "row": int(row_number),
        "written_values": normalized,
    }


def _payment_sheet_id_map(service) -> dict[str, int]:
    metadata = service.spreadsheets().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    mapping: dict[str, int] = {}
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {})
        title = str(props.get("title") or "").strip()
        sheet_id = props.get("sheetId")
        if title and sheet_id is not None:
            mapping[title] = int(sheet_id)
    return mapping


def _payment_row_from_raw(raw: list[str], source_sheet: str, row_index: int) -> dict:
    padded = raw + [""] * max(0, 14 - len(raw))
    row = _normalize_payment_transfer_row(
        {
            "invoice_date": padded[0],
            "customer_name": padded[1],
            "payment_terms_days": padded[2],
            "payment_direction": padded[3],
            "amount": padded[4],
            "po_number": padded[5],
            "delivery_number": padded[6],
            "proforma_invoice_number": padded[7],
            "tax_invoice_number": padded[8],
            "receipt_number": padded[9],
            "notes": padded[10],
            "due_date": padded[11],
            "paid": padded[12],
            "source_mode": padded[13],
        },
        source_sheet=source_sheet,
    )
    row["_sheet_row"] = row_index
    return row


def _payment_rows_match_exact(row_a: dict, row_b: dict) -> bool:
    for field in PAYMENTS_FIELDS:
        if str(row_a.get(field) or "").strip() != str(row_b.get(field) or "").strip():
            return False
    return True


def delete_payment_transfer_row(sheet_title: str, row_number: int, row: dict | None = None, exact_only: bool = False) -> dict:
    service = _service()
    _ensure_payment_sheet_schema(service, sheet_title)

    target_row: dict | None = None
    if row:
        target_row = _normalize_payment_transfer_row(
            {
                **row,
                "_sheet_title": sheet_title,
                "_sheet_row": int(row_number),
            },
            source_sheet=sheet_title,
        )
    else:
        values = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"'{sheet_title}'!A{int(row_number)}:N{int(row_number)}",
        ).execute().get("values", [])
        if values:
            target_row = _payment_row_from_raw(values[0], sheet_title, int(row_number))

    if not target_row:
        raise ValueError("לא הצלחתי לאתר את השורה למחיקה.")

    deletions: dict[str, list[int]] = {}
    if not exact_only:
        for title in _payment_sheet_names(service):
            _ensure_payment_sheet_schema(service, title)
            values = service.spreadsheets().values().get(
                spreadsheetId=settings.google_sheets_spreadsheet_id,
                range=f"'{title}'!A:N",
            ).execute().get("values", [])
            for candidate_row_number, raw in enumerate(values, start=1):
                if not _is_payment_data_row(raw):
                    continue
                candidate = _payment_row_from_raw(raw, title, candidate_row_number)
                if _payment_rows_match_exact(candidate, target_row):
                    deletions.setdefault(title, []).append(candidate_row_number)

    if not deletions:
        deletions = {sheet_title: [int(row_number)]}

    sheet_ids = _payment_sheet_id_map(service)
    deleted_rows = 0
    for title, rows in deletions.items():
        sheet_id = sheet_ids.get(title)
        if sheet_id is None:
            continue
        requests = [
            {
                "deleteDimension": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "ROWS",
                        "startIndex": candidate_row - 1,
                        "endIndex": candidate_row,
                    }
                }
            }
            for candidate_row in sorted(set(int(r) for r in rows), reverse=True)
        ]
        if not requests:
            continue
        service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body={"requests": requests},
        ).execute()
        deleted_rows += len(requests)
        _ensure_payment_sheet_schema(service, title)

    _delete_payment_transfer_cache_rows(target_row, sorted(deletions.keys()))

    return {
        "sheet": sheet_title,
        "row": int(row_number),
        "deleted_rows": deleted_rows,
        "deleted_sheets": sorted(deletions.keys()),
    }


def sync_payment_transfer_receipt_by_invoice_number(invoice_number: str, receipt_number: str, paid: str | bool = True) -> dict:
    normalized_invoice = str(invoice_number or "").strip()
    normalized_receipt = str(receipt_number or "").strip()
    if not normalized_invoice:
        return {"updated_rows": 0, "receipt_number": normalized_receipt, "invoice_number": normalized_invoice}

    service = _service()
    updates: list[dict] = []
    updated_rows = 0

    for title in _payment_sheet_names(service):
        _ensure_payment_sheet_schema(service, title)
        values = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"'{title}'!A:M",
        ).execute().get("values", [])

        for row_index, raw in enumerate(values, start=1):
            if not _is_payment_data_row(raw):
                continue
            padded = raw + [""] * max(0, 13 - len(raw))
            row_invoice = str(padded[8] or "").strip()
            if row_invoice != normalized_invoice:
                continue
            updates.append({
                "range": f"'{title}'!J{row_index}:M{row_index}",
                "values": [[
                    normalized_receipt,
                    padded[10] if len(padded) > 10 else "",
                    padded[11] if len(padded) > 11 else "",
                    _normalize_paid_value(str(paid)),
                ]],
            })
            updated_rows += 1

    _batch_update_payment_rows(service, updates)
    normalized_paid = _normalize_paid_value(str(paid))
    cached = _get_cached_payments_transfer_state()
    if cached and updated_rows:
        all_rows = [dict(item) for item in (cached.get("all_rows") or [])]
        changed = False
        for row in all_rows:
            if str(row.get("tax_invoice_number") or "").strip() != normalized_invoice:
                continue
            row["receipt_number"] = normalized_receipt
            row["paid"] = normalized_paid
            changed = True
        if changed:
            _cache_payments_transfer_state(
                _build_payment_transfer_state(
                    all_rows,
                    sheet_names=cached.get("sheet_names") or [],
                    current_sheet=str(cached.get("current_sheet") or _payment_current_sheet_name()),
                )
            )
    return {
        "invoice_number": normalized_invoice,
        "receipt_number": normalized_receipt,
        "updated_rows": updated_rows,
        "paid": normalized_paid,
    }


def update_payment_transfer_receipt(sheet_title: str, row_number: int, receipt_number: str, paid: str | bool = True) -> dict:
    service = _service()
    _ensure_payment_sheet_schema(service, sheet_title)
    normalized_receipt = str(receipt_number or "").strip()
    normalized_paid = _normalize_paid_value(str(paid))
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [
                {
                    "range": f"'{sheet_title}'!J{int(row_number)}",
                    "values": [[normalized_receipt]],
                },
                {
                    "range": f"'{sheet_title}'!M{int(row_number)}",
                    "values": [[normalized_paid]],
                },
            ],
        },
    ).execute()
    _update_payment_transfer_cache_by_sheet_row(
        sheet_title,
        int(row_number),
        lambda row: (
            row.__setitem__("receipt_number", normalized_receipt),
            row.__setitem__("paid", normalized_paid),
        ),
    )
    return {
        "sheet": sheet_title,
        "row": int(row_number),
        "receipt_number": normalized_receipt,
        "paid": normalized_paid,
    }


def batch_update_payment_transfer_receipts(updates: list[dict]) -> dict:
    if not updates:
        return {"updated_rows": 0}

    service = _service()
    data = []
    updated_rows = 0
    for update in updates:
        sheet_title = str(update.get("sheet_title") or "").strip()
        row_number = int(update.get("row_number") or 0)
        if not sheet_title or row_number <= 0:
            continue
        normalized_receipt = str(update.get("receipt_number") or "").strip()
        normalized_paid = _normalize_paid_value(str(update.get("paid") or ""))
        data.extend(
            [
                {
                    "range": f"'{sheet_title}'!J{row_number}",
                    "values": [[normalized_receipt]],
                },
                {
                    "range": f"'{sheet_title}'!M{row_number}",
                    "values": [[normalized_paid]],
                },
            ]
        )
        updated_rows += 1

    if not data:
        return {"updated_rows": 0}

    service.spreadsheets().values().batchUpdate(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": data,
        },
    ).execute()
    cached = _get_cached_payments_transfer_state()
    if cached:
        all_rows = [dict(item) for item in (cached.get("all_rows") or [])]
        changed = False
        updates_by_key = {
            (str(item.get("sheet_title") or "").strip(), int(item.get("row_number") or 0)): {
                "receipt_number": str(item.get("receipt_number") or "").strip(),
                "paid": _normalize_paid_value(str(item.get("paid") or "")),
            }
            for item in updates
            if str(item.get("sheet_title") or "").strip() and int(item.get("row_number") or 0) > 0
        }
        for row in all_rows:
            key = (str(row.get("_sheet_title") or "").strip(), int(row.get("_sheet_row") or 0))
            if key not in updates_by_key:
                continue
            patch = updates_by_key[key]
            row["receipt_number"] = patch["receipt_number"]
            row["paid"] = patch["paid"]
            changed = True
        if changed:
            _cache_payments_transfer_state(
                _build_payment_transfer_state(
                    all_rows,
                    sheet_names=cached.get("sheet_names") or [],
                    current_sheet=str(cached.get("current_sheet") or _payment_current_sheet_name()),
                )
            )
    return {"updated_rows": updated_rows}


def _inventory_tab_name(kind: str) -> str:
    if kind == "contacts":
        return settings.google_sheets_inventory_contacts_tab
    if kind == "finish":
        return settings.google_sheets_inventory_finish_tab
    return settings.google_sheets_inventory_raw_tab


def _inventory_headers(kind: str):
    if kind == "contacts":
        return CONTACTS_HEADERS
    return FINISH_INVENTORY_HEADERS if kind == "finish" else RAW_INVENTORY_HEADERS


def _inventory_fields(kind: str):
    if kind == "contacts":
        return CONTACTS_FIELDS
    return FINISH_INVENTORY_FIELDS if kind == "finish" else RAW_INVENTORY_FIELDS


def _delivery_tab_name(kind: str) -> str:
    if kind == "contacts":
        return settings.google_sheets_delivery_contacts_tab
    return settings.google_sheets_delivery_confirmations_tab


def _delivery_headers(kind: str):
    if kind == "contacts":
        return DELIVERY_CONTACT_HEADERS
    return DELIVERY_CONFIRMATION_HEADERS


def _delivery_fields(kind: str):
    if kind == "contacts":
        return DELIVERY_CONTACT_FIELDS
    return DELIVERY_CONFIRMATION_FIELDS


def _delivery_confirmation_suppression_key(
    *,
    company: str = "",
    po_number: str = "",
    source_mode: str = "",
    tax_invoice_number: str = "",
    delivery_document_number: str = "",
) -> str:
    normalized_company = _canonical_income_customer_name(company) or str(company or "").strip()
    normalized_po_number = str(po_number or "").strip()
    if re.fullmatch(r"\d+", normalized_po_number):
        try:
            normalized_po_number = str(int(normalized_po_number))
        except Exception:
            normalized_po_number = normalized_po_number.lstrip("0") or "0"
    return "||".join(
        [
            normalized_company,
            normalized_po_number,
            str(source_mode or "").strip().upper(),
            str(tax_invoice_number or "").strip(),
            str(delivery_document_number or "").strip(),
        ]
    )


def _load_delivery_confirmation_suppressions() -> set[str]:
    try:
        if _supabase_enabled_for("app_delivery_confirmation_suppressions"):
            rows = supabase_store.fetch_domain_rows("app_delivery_confirmation_suppressions")
            if rows:
                payload = rows[0] if isinstance(rows[0], dict) else {}
                items = payload.get("values") or payload.get("suppressed_keys") or []
                if isinstance(items, list):
                    return {str(item or "").strip() for item in items if str(item or "").strip()}
        if not _DELIVERY_CONFIRMATION_SUPPRESSIONS_FILE.exists():
            return set()
        payload = json.loads(_DELIVERY_CONFIRMATION_SUPPRESSIONS_FILE.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            return set()
        return {str(item or "").strip() for item in payload if str(item or "").strip()}
    except Exception:
        return set()


def _save_delivery_confirmation_suppressions(values: set[str]) -> None:
    normalized_values = sorted({str(item or "").strip() for item in values if str(item or "").strip()})
    if _supabase_enabled_for("app_delivery_confirmation_suppressions"):
        try:
            supabase_store.replace_domain_rows(
                "app_delivery_confirmation_suppressions",
                [{"values": normalized_values, "updated_at": datetime.now().isoformat(timespec="seconds")}],
            )
        except Exception:
            pass
    try:
        _DELIVERY_CONFIRMATION_SUPPRESSIONS_FILE.write_text(
            json.dumps(normalized_values, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def add_delivery_confirmation_suppression(**kwargs) -> str:
    key = _delivery_confirmation_suppression_key(**kwargs)
    if not key.replace("|", "").strip():
        return ""
    values = _load_delivery_confirmation_suppressions()
    values.add(key)
    _save_delivery_confirmation_suppressions(values)
    return key


def remove_delivery_confirmation_suppression(**kwargs) -> str:
    key = _delivery_confirmation_suppression_key(**kwargs)
    values = _load_delivery_confirmation_suppressions()
    if key in values:
        values.remove(key)
        _save_delivery_confirmation_suppressions(values)
    return key


def _customers_tab_name(kind: str = "active") -> str:
    if kind == "inactive":
        return settings.google_sheets_inactive_customers_tab
    return settings.google_sheets_customers_tab


def _order_history_tab_name() -> str:
    return settings.google_sheets_order_history_tab


def _marketing_tab_name(kind: str) -> str:
    if kind == "finance_invoices":
        return settings.google_sheets_finance_invoices_tab
    if kind == "finance_settings":
        return settings.google_sheets_finance_settings_tab
    if kind == "finance_customer_withholdings":
        return settings.google_sheets_finance_customer_withholdings_tab
    if kind == "finance_bank_movements":
        return settings.google_sheets_finance_bank_movements_tab
    if kind == "pipeline":
        return settings.google_sheets_marketing_pipeline_tab
    if kind == "work_managers":
        return settings.google_sheets_marketing_work_managers_tab
    if kind == "construction_companies":
        return settings.google_sheets_marketing_construction_companies_tab
    if kind == "notes":
        return settings.google_sheets_marketing_notes_tab
    if kind == "reminders":
        return settings.google_sheets_marketing_reminders_tab
    return settings.google_sheets_marketing_history_tab


def _pricing_tab_name(kind: str) -> str:
    if kind == "components":
        return settings.google_sheets_pricing_components_tab
    return settings.google_sheets_pricing_items_tab


def _pricing_headers(kind: str):
    return PRICING_COMPONENT_HEADERS if kind == "components" else PRICING_ITEM_HEADERS


def _pricing_fields(kind: str):
    return PRICING_COMPONENT_FIELDS if kind == "components" else PRICING_ITEM_FIELDS


def _marketing_headers(kind: str) -> list[str]:
    if kind == "finance_invoices":
        return FINANCE_INVOICE_HEADERS
    if kind == "finance_settings":
        return FINANCE_SETTINGS_HEADERS
    if kind == "finance_customer_withholdings":
        return FINANCE_CUSTOMER_WITHHOLDINGS_HEADERS
    if kind == "finance_bank_movements":
        return FINANCE_BANK_MOVEMENTS_HEADERS
    if kind == "pipeline":
        return MARKETING_PIPELINE_HEADERS
    if kind == "work_managers":
        return MARKETING_WORK_MANAGER_HEADERS
    if kind == "construction_companies":
        return MARKETING_CONSTRUCTION_COMPANY_HEADERS
    if kind == "notes":
        return MARKETING_NOTE_HEADERS
    if kind == "reminders":
        return MARKETING_REMINDER_HEADERS
    return MARKETING_HISTORY_HEADERS


def _marketing_fields(kind: str) -> list[str]:
    if kind == "finance_invoices":
        return FINANCE_INVOICE_FIELDS
    if kind == "finance_settings":
        return FINANCE_SETTINGS_FIELDS
    if kind == "finance_customer_withholdings":
        return FINANCE_CUSTOMER_WITHHOLDINGS_FIELDS
    if kind == "finance_bank_movements":
        return FINANCE_BANK_MOVEMENTS_FIELDS
    if kind == "pipeline":
        return MARKETING_PIPELINE_FIELDS
    if kind == "work_managers":
        return MARKETING_WORK_MANAGER_FIELDS
    if kind == "construction_companies":
        return MARKETING_CONSTRUCTION_COMPANY_FIELDS
    if kind == "notes":
        return MARKETING_NOTE_FIELDS
    if kind == "reminders":
        return MARKETING_REMINDER_FIELDS
    return MARKETING_HISTORY_FIELDS


def _ensure_customers_sheet(service, kind: str = "active"):
    title = _customers_tab_name(kind)
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    if first_row != CUSTOMER_HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [CUSTOMER_HEADERS]},
        ).execute()
    _SHEET_ENSURED_CACHE.add(title)
    return title, sheet_id


def _ensure_order_history_sheet(service):
    title = _order_history_tab_name()
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    if first_row != ORDER_HISTORY_HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [ORDER_HISTORY_HEADERS]},
        ).execute()
    _SHEET_ENSURED_CACHE.add(title)
    return title, sheet_id


def _ensure_quote_history_sheet(service):
    title = settings.google_sheets_quote_history_tab
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    if first_row != QUOTE_HISTORY_HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [QUOTE_HISTORY_HEADERS]},
        ).execute()
    _SHEET_ENSURED_CACHE.add(title)
    return title, sheet_id


def _installations_tab_name(kind: str) -> str:
    return (
        settings.google_sheets_installation_visits_tab
        if str(kind or "").strip().lower() == "visits"
        else settings.google_sheets_installation_cases_tab
    )


def _ensure_installations_sheet(service, kind: str):
    title = _installations_tab_name(kind)
    headers = INSTALLATION_VISIT_HEADERS if str(kind or "").strip().lower() == "visits" else INSTALLATION_CASE_HEADERS
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

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


def _ensure_pazomat_sheet(service):
    title = settings.google_sheets_pazomat_tab
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    if first_row != PAZOMAT_HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [PAZOMAT_HEADERS]},
        ).execute()
    _SHEET_ENSURED_CACHE.add(title)
    return title, sheet_id


def _ensure_sibus_sheet(service):
    title = settings.google_sheets_sibus_tab
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    if first_row != SIBUS_HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [SIBUS_HEADERS]},
        ).execute()
    _SHEET_ENSURED_CACHE.add(title)
    return title, sheet_id


def _ensure_supplier_delivery_note_sheet(service):
    title = settings.google_sheets_supplier_delivery_notes_tab
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    if first_row != SUPPLIER_DELIVERY_NOTE_HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [SUPPLIER_DELIVERY_NOTE_HEADERS]},
        ).execute()
    _SHEET_ENSURED_CACHE.add(title)
    return title, sheet_id


def _ensure_inventory_purchase_orders_sheet(service):
    title = settings.google_sheets_inventory_purchase_orders_tab
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    if first_row != INVENTORY_PURCHASE_ORDER_HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [INVENTORY_PURCHASE_ORDER_HEADERS]},
        ).execute()
    _SHEET_ENSURED_CACHE.add(title)
    return title, sheet_id


def _ensure_working_orders_sheet(service):
    title = settings.google_sheets_working_orders_tab
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    if first_row != WORKING_ORDER_HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [WORKING_ORDER_HEADERS]},
        ).execute()
    _SHEET_ENSURED_CACHE.add(title)
    return title, sheet_id


def _ensure_pricing_sheet(service, kind: str):
    title = _pricing_tab_name(kind)
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    headers = _pricing_headers(kind)
    if first_row != headers:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()
    _SHEET_ENSURED_CACHE.add(title)
    return title, sheet_id


def _ensure_marketing_sheet(service, kind: str):
    title = _marketing_tab_name(kind)
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    headers = _marketing_headers(kind)
    if first_row != headers:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()
    _SHEET_ENSURED_CACHE.add(title)
    return title, sheet_id


def _normalize_customer_bool(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"1", "true", "yes", "on", "active"}:
        return "TRUE"
    if lowered in {"0", "false", "no", "off", "inactive"}:
        return "FALSE"
    return str(value or "").strip().upper()


def _normalize_customer_amount(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    cleaned = re.sub(r"[^\d.\-]", "", raw)
    try:
        return f"{float(cleaned):.2f}"
    except Exception:
        return raw


def _normalize_customer_emails(value) -> str:
    if isinstance(value, list):
        parts = [str(item or "").strip() for item in value if str(item or "").strip()]
    else:
        parts = re.split(r"[;,]+", str(value or ""))
    normalized: list[str] = []
    seen: set[str] = set()
    for part in parts:
        email = str(part or "").strip()
        lowered = email.lower()
        if not email or lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(email)
    return ", ".join(normalized)


def _normalize_customer_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in CUSTOMER_FIELDS}
    normalized["customer_guid"] = str(normalized.get("customer_guid") or "").strip()
    normalized["customer_name"] = _canonical_income_customer_name(normalized.get("customer_name", "")) or str(normalized.get("customer_name") or "").strip()
    normalized["customer_id"] = re.sub(r"\D+", "", str(normalized.get("customer_id") or ""))
    normalized["source_mode"] = _normalize_customer_source_mode(normalized.get("source_mode", ""))
    normalized["active"] = _normalize_customer_bool(normalized.get("active", ""))
    normalized["send"] = _normalize_customer_bool(normalized.get("send", ""))
    normalized["payment_terms_days"] = re.sub(r"[^\d\-]", "", str(normalized.get("payment_terms_days") or ""))
    normalized["emails"] = _normalize_customer_emails(normalized.get("emails", ""))
    normalized["income_amount"] = _normalize_customer_amount(normalized.get("income_amount", ""))
    normalized["payment_amount"] = _normalize_customer_amount(normalized.get("payment_amount", ""))
    normalized["balance_amount"] = _normalize_customer_amount(normalized.get("balance_amount", ""))
    normalized["creation_date"] = str(normalized.get("creation_date") or "").strip()
    normalized["last_update_date"] = str(normalized.get("last_update_date") or "").strip()
    normalized["customer_domain"] = _normalize_customer_domain(normalized.get("customer_domain", ""))
    normalized["synced_at"] = str(normalized.get("synced_at") or datetime.now().isoformat(timespec="seconds"))
    normalized["bank_details_updated_sent"] = _normalize_customer_bool(normalized.get("bank_details_updated_sent", ""))
    return normalized


def _normalize_order_history_mode(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"sb", "sandbox"}:
        return "SB"
    if lowered in {"prod", "production", "real", "אמיתי"}:
        return "PROD"
    return str(value or "").strip().upper()


def _normalize_order_history_input_source(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"manual", "ידני", "manual_entry"}:
        return "ידני"
    if lowered in {"file", "upload", "file_upload", "קובץ"}:
        return "קובץ"
    return str(value or "").strip()


def _normalize_order_history_sent(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"אושר ידנית", "אושר", "manual_approved", "manual-approved"}:
        return "אושר ידנית"
    if lowered in {"1", "true", "yes", "כן"}:
        return "כן"
    if lowered in {"0", "false", "no", "לא"}:
        return "לא"
    return str(value or "").strip() or "לא"


def _normalize_order_history_requires_installation(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"1", "true", "yes", "כן"}:
        return "TRUE"
    if lowered in {"0", "false", "no", "לא"}:
        return "FALSE"
    return ""


def _normalize_order_history_document_links(value) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return "[]"
        try:
            parsed = json.loads(raw)
        except Exception:
            return "[]"
    elif isinstance(value, list):
        parsed = value
    else:
        parsed = []
    normalized_items: list[dict] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("label") or "").strip()
        url = str(item.get("url") or item.get("web_view_link") or item.get("webContentLink") or "").strip()
        if not name and not url:
            continue
        normalized_items.append({"name": name, "url": url})
    return json.dumps(normalized_items, ensure_ascii=False)


def _normalize_json_array_value(value) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return "[]"
        try:
            parsed = json.loads(raw)
        except Exception:
            return "[]"
    elif isinstance(value, list):
        parsed = value
    else:
        parsed = []
    normalized_items: list[dict] = []
    for item in parsed:
        if isinstance(item, dict):
            normalized_items.append({str(key): value for key, value in item.items()})
    return json.dumps(normalized_items, ensure_ascii=False)


def _normalize_order_history_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in ORDER_HISTORY_FIELDS}
    normalized["history_id"] = str(normalized.get("history_id") or "").strip()
    normalized["created_at"] = str(normalized.get("created_at") or "").strip()
    normalized["input_source"] = _normalize_order_history_input_source(normalized.get("input_source", ""))
    normalized["mode"] = _normalize_order_history_mode(normalized.get("mode", ""))
    normalized["customer_name"] = _canonical_income_customer_name(normalized.get("customer_name", "")) or str(normalized.get("customer_name") or "").strip()
    normalized["customer_id"] = re.sub(r"\D+", "", str(normalized.get("customer_id") or ""))
    normalized["customer_email"] = str(normalized.get("customer_email") or "").strip()
    normalized["customer_phone"] = str(normalized.get("customer_phone") or "").strip()
    normalized["delivery_address"] = str(normalized.get("delivery_address") or "").strip()
    normalized["project"] = str(normalized.get("project") or "").strip()
    normalized["contact_name"] = str(normalized.get("contact_name") or "").strip()
    normalized["contact_phone"] = str(normalized.get("contact_phone") or "").strip()
    normalized["payment_terms_days"] = str(normalized.get("payment_terms_days") or "").strip()
    normalized["payment_terms_label"] = str(normalized.get("payment_terms_label") or "").strip()
    normalized["po_number"] = str(normalized.get("po_number") or "").strip()
    normalized["quote_number"] = str(normalized.get("quote_number") or "").strip()
    normalized["fulfillment_id"] = str(normalized.get("fulfillment_id") or "").strip()
    raw_document_mode = str(normalized.get("document_mode") or "").strip().lower()
    normalized["document_mode"] = raw_document_mode if raw_document_mode in {"full", "delivery_only", "invoice_only"} else "full"
    normalized["order_status_tag"] = str(normalized.get("order_status_tag") or "").strip()
    normalized["delivery_document_number"] = str(normalized.get("delivery_document_number") or "").strip()
    normalized["delivery_document_id"] = str(normalized.get("delivery_document_id") or "").strip()
    normalized["tax_invoice_number"] = str(normalized.get("tax_invoice_number") or "").strip()
    normalized["tax_invoice_document_id"] = str(normalized.get("tax_invoice_document_id") or "").strip()
    normalized["item_description"] = str(normalized.get("item_description") or "").strip()
    normalized["item_sku"] = str(normalized.get("item_sku") or "").strip()
    normalized["item_unit"] = str(normalized.get("item_unit") or "").strip()
    normalized["item_quantity"] = str(normalized.get("item_quantity") or "").strip()
    normalized["item_unit_price"] = str(normalized.get("item_unit_price") or "").strip()
    normalized["item_line_total"] = str(normalized.get("item_line_total") or "").strip()
    normalized["subtotal"] = str(normalized.get("subtotal") or "").strip()
    normalized["vat"] = str(normalized.get("vat") or "").strip()
    normalized["total"] = str(normalized.get("total") or "").strip()
    normalized["footer_text"] = str(normalized.get("footer_text") or "").strip()
    normalized["items_json"] = _normalize_json_array_value(normalized.get("items_json", "[]"))
    normalized["label_split_rows_json"] = _normalize_json_array_value(normalized.get("label_split_rows_json", "[]"))
    normalized["order_drive_folder_id"] = str(normalized.get("order_drive_folder_id") or "").strip()
    normalized["order_drive_folder_url"] = str(normalized.get("order_drive_folder_url") or "").strip()
    normalized["delivery_drive_file_id"] = str(normalized.get("delivery_drive_file_id") or "").strip()
    normalized["invoice_drive_file_id"] = str(normalized.get("invoice_drive_file_id") or "").strip()
    normalized["merged_drive_file_id"] = str(normalized.get("merged_drive_file_id") or "").strip()
    normalized["coc_drive_file_id"] = str(normalized.get("coc_drive_file_id") or "").strip()
    normalized["document_links_json"] = _normalize_order_history_document_links(normalized.get("document_links_json", "[]"))
    normalized["delivery_confirmation_sent"] = _normalize_order_history_sent(normalized.get("delivery_confirmation_sent", "לא"))
    normalized["po_date"] = str(normalized.get("po_date") or "").strip()
    normalized["items_json"] = _normalize_json_array_value(normalized.get("items_json", "[]"))
    if (
        not normalized["items_json"].strip("[]")
        and normalized["item_description"]
        and normalized["item_quantity"]
    ):
        normalized["items_json"] = _normalize_json_array_value(
            json.dumps(
                [
                    {
                        "description": normalized["item_description"],
                        "sku": normalized["item_sku"],
                        "unit": normalized["item_unit"],
                        "quantity": normalized["item_quantity"],
                        "unit_price": normalized["item_unit_price"],
                        "line_total": normalized["item_line_total"],
                    }
                ],
                ensure_ascii=False,
            )
        )
    normalized["ordered_items_json"] = _normalize_json_array_value(normalized.get("ordered_items_json", "[]"))
    if not normalized["ordered_items_json"].strip("[]") and normalized["items_json"].strip("[]"):
        normalized["ordered_items_json"] = normalized["items_json"]
    normalized["requires_installation"] = _normalize_order_history_requires_installation(
        normalized.get("requires_installation", "")
    )
    partial_delivery_raw = str(normalized.get("partial_delivery") or "").strip().lower()
    normalized["partial_delivery"] = "כן" if partial_delivery_raw in {"כן", "true", "1", "partial", "yes"} else "לא"
    normalized["partial_root_history_id"] = str(normalized.get("partial_root_history_id") or "").strip()
    if normalized["partial_delivery"] == "כן" and not normalized["partial_root_history_id"] and normalized["history_id"]:
        normalized["partial_root_history_id"] = normalized["history_id"]
    if not normalized["order_status_tag"] and normalized["document_mode"] == "delivery_only" and not normalized["tax_invoice_number"]:
        normalized["order_status_tag"] = "לא נוצרה חשבונית מס"
    normalized["updated_at"] = str(normalized.get("updated_at") or normalized.get("created_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _is_broken_order_history_row(row: dict) -> bool:
    normalized = _normalize_order_history_row(row)
    customer_name = str(normalized.get("customer_name") or "").strip()
    if not customer_name:
        return False
    if any(
        str(normalized.get(field) or "").strip()
        for field in (
            "po_number",
            "quote_number",
            "delivery_document_number",
            "tax_invoice_number",
            "item_description",
        )
    ):
        return False
    suspicious_values = (
        str(normalized.get("contact_phone") or "").strip(),
        str(normalized.get("customer_email") or "").strip(),
        str(normalized.get("delivery_address") or "").strip(),
    )
    if any("drive.google.com" in value for value in suspicious_values):
        return True
    if any(re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", value) for value in suspicious_values):
        return True
    return False


def _normalize_installation_case_status(value) -> str:
    raw = re.sub(r"\s+", " ", str(value or "").strip())
    if not raw:
        return "ממתין לתיאום"
    normalized_key = raw.replace("-", " ").replace("_", " ").strip().lower()
    mapping = {
        "pending": "ממתין לתיאום",
        "ממתין": "ממתין לתיאום",
        "ממתין לתאום": "ממתין לתיאום",
        "ממתין לתיאום": "ממתין לתיאום",
        "scheduled": "תואם",
        "תואם": "תואם",
        "partial": "הותקן חלקית",
        "partial install": "הותקן חלקית",
        "הותקן חלקית": "הותקן חלקית",
        "completed": "הושלם",
        "הושלם": "הושלם",
        "on hold": "מושהה",
        "hold": "מושהה",
        "מושהה": "מושהה",
        "cancelled": "בוטל",
        "canceled": "בוטל",
        "בוטל": "בוטל",
    }
    return mapping.get(normalized_key, raw)


def _normalize_installation_case_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in INSTALLATION_CASE_FIELDS}
    normalized["installation_id"] = str(normalized.get("installation_id") or uuid4()).strip()
    normalized["root_history_id"] = str(normalized.get("root_history_id") or "").strip()
    normalized["source_history_id"] = str(normalized.get("source_history_id") or "").strip()
    normalized["created_at"] = str(normalized.get("created_at") or datetime.now().isoformat(timespec="seconds")).strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or normalized.get("created_at") or datetime.now().isoformat(timespec="seconds")).strip()
    normalized["source_mode"] = _normalize_order_history_mode(normalized.get("source_mode", ""))
    normalized["po_number"] = str(normalized.get("po_number") or "").strip()
    normalized["po_date"] = str(normalized.get("po_date") or "").strip()
    normalized["customer_name"] = _canonical_income_customer_name(normalized.get("customer_name", "")) or str(normalized.get("customer_name") or "").strip()
    normalized["customer_id"] = re.sub(r"\D+", "", str(normalized.get("customer_id") or ""))
    normalized["customer_email"] = _normalize_customer_emails(normalized.get("customer_email", ""))
    normalized["customer_phone"] = str(normalized.get("customer_phone") or "").strip()
    normalized["delivery_address"] = re.sub(r"\s+", " ", str(normalized.get("delivery_address") or "").strip())
    normalized["project"] = re.sub(r"\s+", " ", str(normalized.get("project") or "").strip())
    normalized["contact_name"] = re.sub(r"\s+", " ", str(normalized.get("contact_name") or "").strip())
    normalized["contact_phone"] = str(normalized.get("contact_phone") or "").strip()
    normalized["payment_terms_days"] = str(normalized.get("payment_terms_days") or "").strip()
    normalized["payment_terms_label"] = re.sub(r"\s+", " ", str(normalized.get("payment_terms_label") or "").strip())
    normalized["status"] = _normalize_installation_case_status(normalized.get("status", ""))
    normalized["delay_reason"] = re.sub(r"\s+", " ", str(normalized.get("delay_reason") or "").strip())
    normalized["next_visit_date"] = str(normalized.get("next_visit_date") or "").strip()
    normalized["last_visit_date"] = str(normalized.get("last_visit_date") or "").strip()
    normalized["visit_count"] = str(int(float(str(normalized.get("visit_count") or "0").strip() or 0)))
    normalized["notes"] = str(normalized.get("notes") or "").strip()
    normalized["order_drive_folder_id"] = str(normalized.get("order_drive_folder_id") or "").strip()
    normalized["order_drive_folder_url"] = str(normalized.get("order_drive_folder_url") or "").strip()
    normalized["source_po_drive_file_id"] = str(normalized.get("source_po_drive_file_id") or "").strip()
    normalized["source_po_drive_url"] = str(normalized.get("source_po_drive_url") or "").strip()
    normalized["delivery_document_number"] = str(normalized.get("delivery_document_number") or "").strip()
    normalized["delivery_document_id"] = str(normalized.get("delivery_document_id") or "").strip()
    normalized["tax_invoice_number"] = str(normalized.get("tax_invoice_number") or "").strip()
    normalized["tax_invoice_document_id"] = str(normalized.get("tax_invoice_document_id") or "").strip()
    normalized["delivery_drive_file_id"] = str(normalized.get("delivery_drive_file_id") or "").strip()
    normalized["invoice_drive_file_id"] = str(normalized.get("invoice_drive_file_id") or "").strip()
    normalized["merged_drive_file_id"] = str(normalized.get("merged_drive_file_id") or "").strip()
    normalized["coc_drive_file_id"] = str(normalized.get("coc_drive_file_id") or "").strip()
    normalized["document_links_json"] = _normalize_order_history_document_links(normalized.get("document_links_json", "[]"))
    normalized["install_items_json"] = _normalize_json_array_value(normalized.get("install_items_json", "[]"))
    normalized["installed_items_json"] = _normalize_json_array_value(normalized.get("installed_items_json", "[]"))
    normalized["remaining_items_json"] = _normalize_json_array_value(normalized.get("remaining_items_json", "[]"))
    for amount_field in ("total_ordered_quantity", "total_installed_quantity", "total_remaining_quantity"):
        raw = str(normalized.get(amount_field) or "").strip().replace(",", "")
        try:
            normalized[amount_field] = f"{float(raw):.2f}" if raw else "0.00"
        except Exception:
            normalized[amount_field] = raw or "0.00"
    normalized["source_active"] = "לא" if str(normalized.get("source_active") or "").strip() in {"לא", "false", "FALSE", "0"} else "כן"
    normalized["last_sync_at"] = str(normalized.get("last_sync_at") or normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds")).strip()
    return normalized


def _normalize_installation_visit_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in INSTALLATION_VISIT_FIELDS}
    normalized["visit_id"] = str(normalized.get("visit_id") or uuid4()).strip()
    normalized["installation_id"] = str(normalized.get("installation_id") or "").strip()
    normalized["created_at"] = str(normalized.get("created_at") or datetime.now().isoformat(timespec="seconds")).strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or normalized.get("created_at") or datetime.now().isoformat(timespec="seconds")).strip()
    normalized["visit_date"] = str(normalized.get("visit_date") or "").strip()
    normalized["scheduled_date"] = str(normalized.get("scheduled_date") or "").strip()
    normalized["status"] = _normalize_installation_case_status(normalized.get("status", ""))
    normalized["installed_items_json"] = _normalize_json_array_value(normalized.get("installed_items_json", "[]"))
    raw_total = str(normalized.get("installed_total_quantity") or "").strip().replace(",", "")
    try:
        normalized["installed_total_quantity"] = f"{float(raw_total):.2f}" if raw_total else "0.00"
    except Exception:
        normalized["installed_total_quantity"] = raw_total or "0.00"
    normalized["notes"] = str(normalized.get("notes") or "").strip()
    normalized["summary_text"] = re.sub(r"\s+", " ", str(normalized.get("summary_text") or "").strip())
    return normalized


def _normalize_quote_history_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in QUOTE_HISTORY_FIELDS}
    normalized["history_id"] = str(normalized.get("history_id") or "").strip()
    normalized["created_at"] = str(normalized.get("created_at") or "").strip()
    normalized["input_source"] = _normalize_order_history_input_source(normalized.get("input_source", ""))
    normalized["mode"] = _normalize_order_history_mode(normalized.get("mode", ""))
    normalized["customer_name"] = _canonical_income_customer_name(normalized.get("customer_name", "")) or str(normalized.get("customer_name") or "").strip()
    normalized["customer_id"] = re.sub(r"\D+", "", str(normalized.get("customer_id") or ""))
    normalized["po_number"] = str(normalized.get("po_number") or "").strip()
    normalized["quote_number"] = str(normalized.get("quote_number") or "").strip()
    normalized["quote_document_id"] = str(normalized.get("quote_document_id") or "").strip()
    normalized["quote_date"] = str(normalized.get("quote_date") or "").strip()
    normalized["customer_email"] = str(normalized.get("customer_email") or "").strip()
    normalized["customer_phone"] = str(normalized.get("customer_phone") or "").strip()
    normalized["delivery_address"] = str(normalized.get("delivery_address") or "").strip()
    normalized["project"] = str(normalized.get("project") or "").strip()
    normalized["contact_name"] = str(normalized.get("contact_name") or "").strip()
    normalized["contact_phone"] = str(normalized.get("contact_phone") or "").strip()
    normalized["payment_terms_days"] = str(normalized.get("payment_terms_days") or "").strip()
    normalized["payment_terms_label"] = str(normalized.get("payment_terms_label") or "").strip()
    normalized["item_description"] = str(normalized.get("item_description") or "").strip()
    normalized["item_sku"] = str(normalized.get("item_sku") or "").strip()
    normalized["item_unit"] = str(normalized.get("item_unit") or "").strip()
    normalized["item_quantity"] = str(normalized.get("item_quantity") or "").strip()
    normalized["item_unit_price"] = str(normalized.get("item_unit_price") or "").strip()
    normalized["item_line_total"] = str(normalized.get("item_line_total") or "").strip()
    normalized["subtotal"] = str(normalized.get("subtotal") or "").strip()
    normalized["vat"] = str(normalized.get("vat") or "").strip()
    normalized["total"] = str(normalized.get("total") or "").strip()
    normalized["footer_text"] = str(normalized.get("footer_text") or "").strip()
    normalized["label_split_rows_json"] = _normalize_json_array_value(normalized.get("label_split_rows_json", "[]"))
    normalized["quote_drive_folder_id"] = str(normalized.get("quote_drive_folder_id") or "").strip()
    normalized["quote_drive_folder_url"] = str(normalized.get("quote_drive_folder_url") or "").strip()
    normalized["document_links_json"] = _normalize_order_history_document_links(normalized.get("document_links_json", "[]"))
    normalized["quote_mail_status"] = str(normalized.get("quote_mail_status") or "").strip().lower()
    normalized["quote_mail_sent_at"] = str(normalized.get("quote_mail_sent_at") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or normalized.get("created_at") or datetime.now().isoformat(timespec="seconds"))
    # Backward-compatibility for rows written before the expanded schema.
    if (
        not normalized["quote_drive_folder_id"]
        and not normalized["quote_drive_folder_url"]
        and not normalized["document_links_json"].strip("[]")
        and normalized["customer_email"]
        and normalized["customer_phone"].startswith("https://drive.google.com/drive/folders/")
        and normalized["delivery_address"].startswith("[")
        and re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", normalized["project"] or "")
    ):
        normalized["quote_drive_folder_id"] = normalized["customer_email"]
        normalized["quote_drive_folder_url"] = normalized["customer_phone"]
        normalized["document_links_json"] = _normalize_order_history_document_links(normalized["delivery_address"])
        normalized["updated_at"] = normalized["project"] or normalized["updated_at"]
        normalized["customer_email"] = ""
        normalized["customer_phone"] = ""
        normalized["delivery_address"] = ""
        normalized["project"] = ""
    if (
        not normalized["items_json"].strip("[]")
        and normalized["item_description"]
        and normalized["item_quantity"]
    ):
        normalized["items_json"] = _normalize_json_array_value(
            json.dumps(
                [
                    {
                        "description": normalized["item_description"],
                        "sku": normalized["item_sku"],
                        "unit": normalized["item_unit"],
                        "quantity": normalized["item_quantity"],
                        "unit_price": normalized["item_unit_price"],
                        "line_total": normalized["item_line_total"],
                    }
                ],
                ensure_ascii=False,
            )
        )
    return normalized


def _normalize_supplier_delivery_note_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "").strip() for field in SUPPLIER_DELIVERY_NOTE_FIELDS}
    normalized["record_id"] = str(normalized.get("record_id") or "").strip()
    normalized["supplier_name"] = str(normalized.get("supplier_name") or "").strip()
    normalized["parser_name"] = str(normalized.get("parser_name") or "").strip()
    normalized["source_document_name"] = str(normalized.get("source_document_name") or "").strip()
    normalized["delivery_note_number"] = str(normalized.get("delivery_note_number") or "").strip()
    normalized["delivery_date"] = str(normalized.get("delivery_date") or "").strip()
    normalized["customer_name"] = _canonical_income_customer_name(normalized.get("customer_name", "")) or str(normalized.get("customer_name") or "").strip()
    normalized["customer_id"] = re.sub(r"\D+", "", str(normalized.get("customer_id") or ""))
    normalized["delivery_address"] = str(normalized.get("delivery_address") or "").strip()
    normalized["contact_name"] = str(normalized.get("contact_name") or "").strip()
    normalized["contact_phone"] = str(normalized.get("contact_phone") or "").strip()
    normalized["item_index"] = str(normalized.get("item_index") or "").strip()
    normalized["supplier_sku"] = str(normalized.get("supplier_sku") or "").strip()
    normalized["item_description"] = str(normalized.get("item_description") or "").strip()
    normalized["product"] = str(normalized.get("product") or "").strip()
    normalized["material"] = str(normalized.get("material") or "").strip()
    normalized["length"] = str(normalized.get("length") or "").strip()
    normalized["width"] = str(normalized.get("width") or "").strip()
    normalized["thickness"] = str(normalized.get("thickness") or "").strip()
    normalized["quantity"] = _normalize_customer_amount(normalized.get("quantity"))
    normalized["unit"] = str(normalized.get("unit") or "").strip()
    normalized["notes"] = str(normalized.get("notes") or "").strip()
    normalized["source_local_path"] = str(normalized.get("source_local_path") or "").strip()
    normalized["source_drive_file_id"] = str(normalized.get("source_drive_file_id") or "").strip()
    normalized["source_drive_url"] = str(normalized.get("source_drive_url") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_inventory_purchase_order_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "").strip() for field in INVENTORY_PURCHASE_ORDER_FIELDS}
    normalized["history_id"] = str(normalized.get("history_id") or "").strip()
    normalized["created_at"] = str(normalized.get("created_at") or "").strip()
    mode = str(normalized.get("mode") or "").strip().lower()
    normalized["mode"] = "production" if mode in {"production", "prod", "real", "true"} else "sandbox"
    normalized["supplier_name"] = _canonical_income_customer_name(normalized.get("supplier_name", "")) or str(normalized.get("supplier_name") or "").strip()
    normalized["supplier_id"] = re.sub(r"\D+", "", str(normalized.get("supplier_id") or ""))
    normalized["supplier_email"] = str(normalized.get("supplier_email") or "").strip()
    normalized["supplier_phone"] = str(normalized.get("supplier_phone") or "").strip()
    normalized["po_number"] = str(normalized.get("po_number") or "").strip()
    normalized["po_document_id"] = str(normalized.get("po_document_id") or "").strip()
    normalized["po_date"] = str(normalized.get("po_date") or "").strip()
    normalized["item_description"] = str(normalized.get("item_description") or "").strip()
    normalized["item_sku"] = str(normalized.get("item_sku") or "").strip()
    normalized["item_quantity"] = str(normalized.get("item_quantity") or "").strip()
    normalized["item_unit"] = str(normalized.get("item_unit") or "").strip()
    normalized["item_unit_price"] = str(normalized.get("item_unit_price") or "").strip()
    normalized["subtotal"] = str(normalized.get("subtotal") or "").strip()
    normalized["vat"] = str(normalized.get("vat") or "").strip()
    normalized["total"] = str(normalized.get("total") or "").strip()
    normalized["remarks"] = str(normalized.get("remarks") or "").strip()
    normalized["po_local_file"] = str(normalized.get("po_local_file") or "").strip()
    normalized["po_drive_file_id"] = str(normalized.get("po_drive_file_id") or "").strip()
    normalized["po_drive_url"] = str(normalized.get("po_drive_url") or "").strip()
    normalized["drive_folder_id"] = str(normalized.get("drive_folder_id") or "").strip()
    normalized["drive_folder_url"] = str(normalized.get("drive_folder_url") or "").strip()
    normalized["send_status"] = str(normalized.get("send_status") or "").strip().lower()
    normalized["sent_at"] = str(normalized.get("sent_at") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or normalized.get("created_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_working_order_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "").strip() for field in WORKING_ORDER_FIELDS}
    normalized["row_id"] = normalized.get("row_id") or uuid4().hex
    normalized["created_at"] = normalized.get("created_at") or datetime.now().isoformat(timespec="seconds")
    normalized["updated_at"] = normalized.get("updated_at") or normalized.get("created_at") or datetime.now().isoformat(timespec="seconds")
    normalized["customer_name"] = _canonical_income_customer_name(normalized.get("customer_name", "")) or normalized.get("customer_name", "")
    normalized["customer_id"] = re.sub(r"\D+", "", normalized.get("customer_id", ""))
    normalized["po_number"] = str(normalized.get("po_number") or "").strip()
    normalized["po_date"] = str(normalized.get("po_date") or "").strip()
    normalized["item_description"] = str(normalized.get("item_description") or "").strip()
    normalized["item_unit"] = str(normalized.get("item_unit") or "ללא").strip() or "ללא"
    requires_installation = str(normalized.get("requires_installation") or "").strip().lower()
    if requires_installation in {"1", "true", "yes", "כן"}:
        normalized["requires_installation"] = "TRUE"
    elif requires_installation in {"0", "false", "no", "לא"}:
        normalized["requires_installation"] = "FALSE"
    else:
        normalized["requires_installation"] = ""
    normalized["order_note_text"] = str(normalized.get("order_note_text") or "").strip()
    normalized["order_note_file_name"] = str(normalized.get("order_note_file_name") or "").strip()
    normalized["order_note_file_path"] = str(normalized.get("order_note_file_path") or "").strip()
    normalized["order_note_drive_file_id"] = str(normalized.get("order_note_drive_file_id") or "").strip()
    normalized["order_note_drive_url"] = str(normalized.get("order_note_drive_url") or "").strip()
    for numeric_field in ("item_quantity", "item_unit_price", "subtotal", "vat", "total", "items_count"):
        raw_value = str(normalized.get(numeric_field) or "").strip()
        if raw_value in {"", "None"}:
            normalized[numeric_field] = ""
            continue
        try:
            numeric_value = float(raw_value)
        except Exception:
            normalized[numeric_field] = raw_value
            continue
        if numeric_field in {"item_quantity", "items_count"} and numeric_value.is_integer():
            normalized[numeric_field] = str(int(numeric_value))
        else:
            normalized[numeric_field] = f"{numeric_value:.2f}".rstrip("0").rstrip(".")
    return normalized


def _normalize_marketing_note_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in MARKETING_NOTE_FIELDS}
    normalized["customer_key"] = str(normalized.get("customer_key") or "").strip()
    normalized["customer_guid"] = str(normalized.get("customer_guid") or "").strip()
    normalized["customer_id"] = re.sub(r"\D+", "", str(normalized.get("customer_id") or ""))
    normalized["customer_name"] = _canonical_income_customer_name(normalized.get("customer_name", "")) or str(normalized.get("customer_name") or "").strip()
    normalized["note_text"] = str(normalized.get("note_text") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_pricing_item_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "").strip() for field in PRICING_ITEM_FIELDS}
    if not normalized.get("item_id"):
        normalized["item_id"] = datetime.now().strftime("pricing%Y%m%d%H%M%S%f")
    # Old broken saves leaked updated_at values into the notes column. Keep notes manual-only.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", str(normalized.get("notes") or "").strip()):
        normalized["notes"] = ""
    normalized["kind"] = "service" if str(normalized.get("kind") or "").strip().lower() == "service" else "product"
    normalized["pricing_unit"] = str(normalized.get("pricing_unit") or "יחידה").strip() or "יחידה"
    if not normalized.get("dimensions_json"):
        width = str(normalized.get("default_width_m") or "").strip()
        length = str(normalized.get("default_length_m") or "").strip()
        if width or length:
            dimension_id = f"{normalized['item_id']}_dim_1"
            normalized["selected_dimension_id"] = normalized.get("selected_dimension_id") or dimension_id
            normalized["dimensions_json"] = json.dumps(
                [
                    {
                        "dimension_id": dimension_id,
                        "width_m": width,
                        "length_m": length,
                    }
                ],
                ensure_ascii=False,
            )
    normalized["active"] = "FALSE" if str(normalized.get("active") or "").strip().lower() in {"0", "false", "no", "off"} else "TRUE"
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_pricing_component_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "").strip() for field in PRICING_COMPONENT_FIELDS}
    if not normalized.get("component_id"):
        normalized["component_id"] = datetime.now().strftime("component%Y%m%d%H%M%S%f")
    # Old broken saves leaked updated_at values into the notes column. Keep notes manual-only.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", str(normalized.get("notes") or "").strip()):
        normalized["notes"] = ""
    normalized["component_kind"] = str(normalized.get("component_kind") or "חומר גלם").strip() or "חומר גלם"
    normalized["consumption_basis"] = str(normalized.get("consumption_basis") or "ליחידה").strip() or "ליחידה"
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_pazomat_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "").strip() for field in PAZOMAT_FIELDS}
    normalized["month"] = str(normalized.get("month") or "").strip()
    normalized["status"] = str(normalized.get("status") or "").strip() or "missing"
    normalized["gmail_message_id"] = str(normalized.get("gmail_message_id") or "").strip()
    normalized["subject"] = str(normalized.get("subject") or "").strip()
    normalized["source_type"] = str(normalized.get("source_type") or "").strip()
    normalized["invoice_number"] = str(normalized.get("invoice_number") or "").strip()
    normalized["fuel_doc_number"] = str(normalized.get("fuel_doc_number") or "").strip()
    normalized["total_amount"] = _normalize_customer_amount(normalized.get("total_amount"))
    normalized["fuel_amount"] = _normalize_customer_amount(normalized.get("fuel_amount"))
    normalized["service_amount"] = _normalize_customer_amount(normalized.get("service_amount"))
    normalized["debit_date"] = str(normalized.get("debit_date") or "").strip()
    normalized["vehicle_count"] = str(normalized.get("vehicle_count") or "").strip()
    normalized["vehicles_json"] = str(normalized.get("vehicles_json") or "").strip()
    normalized["card_count"] = str(normalized.get("card_count") or "").strip()
    normalized["cards_json"] = str(normalized.get("cards_json") or "").strip()
    normalized["liters_total"] = _normalize_customer_amount(normalized.get("liters_total"))
    normalized["drive_folder_id"] = str(normalized.get("drive_folder_id") or "").strip()
    normalized["drive_folder_url"] = str(normalized.get("drive_folder_url") or "").strip()
    normalized["drive_file_id"] = str(normalized.get("drive_file_id") or "").strip()
    normalized["drive_url"] = str(normalized.get("drive_url") or "").strip()
    normalized["local_path"] = str(normalized.get("local_path") or "").strip()
    normalized["notes"] = str(normalized.get("notes") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _pazomat_sort_key(row: dict) -> tuple[int, int]:
    raw = str((row or {}).get("month") or "").strip()
    try:
        month_text, year_text = raw.split("/", 1)
        return int(year_text), int(month_text)
    except Exception:
        return (9999, 99)


def _normalize_sibus_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "").strip() for field in SIBUS_FIELDS}
    normalized["month"] = str(normalized.get("month") or "").strip()
    normalized["status"] = str(normalized.get("status") or "").strip() or "missing"
    normalized["gmail_message_id"] = str(normalized.get("gmail_message_id") or "").strip()
    normalized["subject"] = str(normalized.get("subject") or "").strip()
    normalized["source_type"] = str(normalized.get("source_type") or "").strip()
    normalized["invoice_number"] = str(normalized.get("invoice_number") or "").strip()
    normalized["invoice_date"] = str(normalized.get("invoice_date") or "").strip()
    normalized["billing_period"] = str(normalized.get("billing_period") or "").strip()
    normalized["due_date"] = str(normalized.get("due_date") or "").strip()
    normalized["subtotal_amount"] = _normalize_customer_amount(normalized.get("subtotal_amount"))
    normalized["vat_amount"] = _normalize_customer_amount(normalized.get("vat_amount"))
    normalized["total_amount"] = _normalize_customer_amount(normalized.get("total_amount"))
    normalized["customer_number"] = str(normalized.get("customer_number") or "").strip()
    normalized["drive_folder_id"] = str(normalized.get("drive_folder_id") or "").strip()
    normalized["drive_folder_url"] = str(normalized.get("drive_folder_url") or "").strip()
    normalized["drive_file_id"] = str(normalized.get("drive_file_id") or "").strip()
    normalized["drive_url"] = str(normalized.get("drive_url") or "").strip()
    normalized["local_path"] = str(normalized.get("local_path") or "").strip()
    normalized["notes"] = str(normalized.get("notes") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _sibus_sort_key(row: dict) -> tuple[int, int]:
    raw = str((row or {}).get("month") or "").strip()
    try:
        month_text, year_text = raw.split("/", 1)
        return int(year_text), int(month_text)
    except Exception:
        return (9999, 99)


def _normalize_marketing_reminder_status(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"done", "completed", "closed", "טופל"}:
        return "טופל"
    if lowered in {"postponed", "deferred", "נדחה"}:
        return "נדחה"
    return "פתוח"


def _normalize_marketing_reminder_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in MARKETING_REMINDER_FIELDS}
    normalized["reminder_id"] = str(normalized.get("reminder_id") or "").strip()
    normalized["customer_key"] = str(normalized.get("customer_key") or "").strip()
    normalized["customer_guid"] = str(normalized.get("customer_guid") or "").strip()
    normalized["customer_id"] = re.sub(r"\D+", "", str(normalized.get("customer_id") or ""))
    normalized["customer_name"] = _canonical_income_customer_name(normalized.get("customer_name", "")) or str(normalized.get("customer_name") or "").strip()
    normalized["contact_name"] = str(normalized.get("contact_name") or "").strip()
    normalized["phone"] = str(normalized.get("phone") or "").strip()
    normalized["emails"] = str(normalized.get("emails") or "").strip()
    normalized["note_text"] = str(normalized.get("note_text") or "").strip()
    normalized["due_date"] = str(normalized.get("due_date") or "").strip()
    normalized["due_time"] = str(normalized.get("due_time") or "").strip() or "09:00"
    normalized["status"] = _normalize_marketing_reminder_status(normalized.get("status", ""))
    normalized["channel"] = str(normalized.get("channel") or "").strip()
    normalized["message"] = str(normalized.get("message") or "").strip()
    normalized["comm_status"] = str(normalized.get("comm_status") or "").strip().lower()
    normalized["comm_sent_at"] = str(normalized.get("comm_sent_at") or "").strip()
    normalized["auto_whatsapp_status"] = str(normalized.get("auto_whatsapp_status") or "").strip().lower()
    normalized["auto_whatsapp_sent_at"] = str(normalized.get("auto_whatsapp_sent_at") or "").strip()
    normalized["created_at"] = str(normalized.get("created_at") or datetime.now().isoformat(timespec="seconds"))
    normalized["completed_at"] = str(normalized.get("completed_at") or "").strip()
    return normalized


def _normalize_marketing_history_details(value) -> str:
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return "{}"
        try:
            parsed = json.loads(raw)
        except Exception:
            return json.dumps({"text": raw}, ensure_ascii=False)
    elif isinstance(value, dict):
        parsed = value
    else:
        parsed = {}
    return json.dumps(parsed, ensure_ascii=False)


def _normalize_marketing_history_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in MARKETING_HISTORY_FIELDS}
    normalized["history_id"] = str(normalized.get("history_id") or "").strip()
    normalized["created_at"] = str(normalized.get("created_at") or datetime.now().isoformat(timespec="seconds"))
    normalized["customer_key"] = str(normalized.get("customer_key") or "").strip()
    normalized["customer_guid"] = str(normalized.get("customer_guid") or "").strip()
    normalized["customer_id"] = re.sub(r"\D+", "", str(normalized.get("customer_id") or ""))
    normalized["customer_name"] = _canonical_income_customer_name(normalized.get("customer_name", "")) or str(normalized.get("customer_name") or "").strip()
    normalized["action_type"] = str(normalized.get("action_type") or "").strip()
    normalized["channel"] = str(normalized.get("channel") or "").strip()
    normalized["subject"] = str(normalized.get("subject") or "").strip()
    normalized["details_json"] = _normalize_marketing_history_details(normalized.get("details_json", "{}"))
    normalized["result"] = str(normalized.get("result") or "").strip()
    return normalized


def _customer_cache_file(kind: str = "active") -> Path:
    return _INACTIVE_CUSTOMERS_CACHE_FILE if kind == "inactive" else _CUSTOMERS_CACHE_FILE


def _marketing_cache_file(kind: str) -> Path:
    if kind == "finance_invoices":
        return _FINANCE_INVOICES_CACHE_FILE
    if kind == "finance_settings":
        return _FINANCE_SETTINGS_CACHE_FILE
    if kind == "finance_customer_withholdings":
        return _FINANCE_CUSTOMER_WITHHOLDINGS_CACHE_FILE
    if kind == "finance_bank_movements":
        return _FINANCE_BANK_MOVEMENTS_CACHE_FILE
    if kind == "pipeline":
        return _MARKETING_PIPELINE_CACHE_FILE
    if kind == "work_managers":
        return _MARKETING_WORK_MANAGERS_CACHE_FILE
    if kind == "construction_companies":
        return _MARKETING_CONSTRUCTION_COMPANIES_CACHE_FILE
    if kind == "notes":
        return _MARKETING_NOTES_CACHE_FILE
    if kind == "reminders":
        return _MARKETING_REMINDERS_CACHE_FILE
    return _MARKETING_HISTORY_CACHE_FILE


def _normalize_marketing_pipeline_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in MARKETING_PIPELINE_FIELDS}
    normalized["customer_key"] = str(normalized.get("customer_key") or "").strip()
    normalized["customer_guid"] = str(normalized.get("customer_guid") or "").strip()
    normalized["customer_id"] = re.sub(r"\D+", "", str(normalized.get("customer_id") or ""))
    normalized["customer_name"] = _canonical_income_customer_name(normalized.get("customer_name", "")) or str(normalized.get("customer_name") or "").strip()
    normalized["quote_number"] = str(normalized.get("quote_number") or "").strip()
    normalized["quote_document_id"] = str(normalized.get("quote_document_id") or "").strip()
    normalized["quote_date"] = str(normalized.get("quote_date") or "").strip()
    normalized["item_name"] = str(normalized.get("item_name") or "").strip()
    normalized["emails"] = _normalize_customer_emails(normalized.get("emails", ""))
    normalized["phone"] = str(normalized.get("phone") or "").strip()
    normalized["contact_name"] = str(normalized.get("contact_name") or "").strip()
    normalized["note_text"] = str(normalized.get("note_text") or "").strip()
    normalized["comm_status"] = str(normalized.get("comm_status") or "").strip().lower()
    normalized["comm_sent_at"] = str(normalized.get("comm_sent_at") or "").strip()
    normalized["mail_subject"] = str(normalized.get("mail_subject") or "").strip()
    normalized["mail_sent_at"] = str(normalized.get("mail_sent_at") or "").strip()
    normalized["quote_drive_url"] = str(normalized.get("quote_drive_url") or "").strip()
    normalized["quote_drive_file_id"] = str(normalized.get("quote_drive_file_id") or "").strip()
    normalized["quote_source_url"] = str(normalized.get("quote_source_url") or "").strip()
    normalized["source"] = str(normalized.get("source") or "").strip() or "greeninvoice"

    def _looks_like_url(value: str) -> bool:
        return str(value or "").strip().startswith(("http://", "https://"))

    def _looks_like_datetime(value: str) -> bool:
        raw = str(value or "").strip()
        if not raw:
            return False
        try:
            parsedate_to_datetime(raw)
            return True
        except Exception:
            pass
        try:
            datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return True
        except Exception:
            return False

    def _looks_like_phone(value: str) -> bool:
        digits = re.sub(r"\D+", "", str(value or ""))
        return 7 <= len(digits) <= 12

    def _looks_like_subject(value: str) -> bool:
        raw = str(value or "").strip()
        lowered = raw.lower()
        if not raw:
            return False
        if raw.startswith(("Re:", "Fwd:", "FW:")):
            return True
        subject_markers = (
            "הצעת מחיר",
            "ברושור",
            "קטלוג",
            "קוואיטפייפ",
            "quietpipe",
            "qtp",
            "בן יעקב פתרונות טקסטיל",
            "סדרת מוצרי",
        )
        return any(marker.lower() in lowered for marker in subject_markers)

    def _looks_like_name(value: str) -> bool:
        raw = str(value or "").strip().strip("*").strip()
        if not raw or _looks_like_url(raw) or _looks_like_datetime(raw) or _looks_like_subject(raw):
            return False
        if "@" in raw:
            return False
        if len(re.findall(r"\d", raw)) >= 4:
            return False
        return 1 <= len(raw) <= 80

    # Repair older rows where drive/source fields drifted into communication columns.
    if _looks_like_url(normalized["comm_status"]) and "drive.google.com" in normalized["comm_status"]:
        if not _looks_like_url(normalized["quote_drive_url"]):
            normalized["quote_drive_url"] = normalized["comm_status"]
        normalized["comm_status"] = ""
    if normalized["comm_sent_at"] and not normalized["quote_drive_file_id"]:
        if re.fullmatch(r"[A-Za-z0-9_-]{20,}", normalized["comm_sent_at"]):
            normalized["quote_drive_file_id"] = normalized["comm_sent_at"]
            normalized["comm_sent_at"] = ""
    if _looks_like_url(normalized["mail_subject"]) and "greeninvoice" in normalized["mail_subject"].lower():
        if not _looks_like_url(normalized["quote_source_url"]):
            normalized["quote_source_url"] = normalized["mail_subject"]
        normalized["mail_subject"] = ""
    if normalized["mail_sent_at"] in {"greeninvoice", "gmail", "sheet", "cache"}:
        normalized["source"] = normalized["mail_sent_at"] or normalized["source"]
        normalized["mail_sent_at"] = ""
    if _looks_like_datetime(normalized["quote_drive_url"]) and _looks_like_url(normalized["comm_status"]):
        normalized["quote_drive_url"] = normalized["comm_status"]
        normalized["comm_status"] = ""

    # Keep notes manual-only; wipe accidental mail dates that leaked into the notes column.
    if _looks_like_datetime(normalized["note_text"]) or _looks_like_url(normalized["note_text"]):
        normalized["note_text"] = ""

    # If a contact name leaked into the phone column, move it back only when the current contact field
    # is clearly not a person name (usually a mail subject from old rows).
    if not _looks_like_phone(normalized["phone"]):
        if _looks_like_name(normalized["phone"]) and not _looks_like_name(normalized["contact_name"]):
            normalized["contact_name"] = normalized["phone"].strip().strip("*").strip()
        normalized["phone"] = ""

    if _looks_like_subject(normalized["contact_name"]) or _looks_like_url(normalized["contact_name"]) or _looks_like_datetime(normalized["contact_name"]):
        normalized["contact_name"] = ""

    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_work_manager_active_status(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"כן", "yes", "true", "1", "active"}:
        return "כן"
    if lowered in {"לא", "no", "false", "0", "inactive"}:
        return "לא"
    return "לא"


def _normalize_work_manager_phone(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    digits = re.sub(r"\D+", "", raw)
    if len(digits) == 10 and digits.startswith("0"):
        return f"{digits[:3]}-{digits[3:]}"
    if len(digits) == 9 and digits.startswith("5"):
        return f"0{digits[:2]}-{digits[2:]}"
    if len(digits) == 9 and digits.startswith("0"):
        return f"{digits[:2]}-{digits[2:]}"
    return raw


def _normalize_work_manager_phone_digits(value: str) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    if len(digits) == 9 and digits.startswith("5"):
        return f"0{digits}"
    return digits


def _split_work_manager_phones(value) -> list[str]:
    if isinstance(value, list):
        raw_parts = [str(item or "").strip() for item in value]
    else:
        raw_parts = re.split(r"[\s,;/|]+", str(value or ""))
    numbers: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        normalized = _normalize_work_manager_phone(part)
        digits = _normalize_work_manager_phone_digits(normalized)
        if not digits or digits in seen:
            continue
        seen.add(digits)
        numbers.append(normalized)
    return numbers[:3]


def _normalize_marketing_work_manager_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in MARKETING_WORK_MANAGER_FIELDS}
    normalized["row_id"] = str(normalized.get("row_id") or uuid4()).strip()
    normalized["full_name"] = re.sub(r"\s+", " ", str(normalized.get("full_name") or "").strip())
    normalized["company_name"] = re.sub(r"\s+", " ", str(normalized.get("company_name") or "").strip())
    normalized["email"] = _normalize_customer_emails(normalized.get("email", ""))
    if not normalized["company_name"] and str(normalized.get("current_employer") or "").strip():
        normalized["company_name"] = re.sub(r"\s+", " ", str(normalized.get("current_employer") or "").strip())
    if not normalized["current_employer"] and normalized["company_name"]:
        normalized["current_employer"] = normalized["company_name"]
    phones = _split_work_manager_phones([
        normalized.get("phone_1", ""),
        normalized.get("phone_2", ""),
        normalized.get("phone_3", ""),
    ])
    normalized["phone_1"] = phones[0] if len(phones) > 0 else ""
    normalized["phone_2"] = phones[1] if len(phones) > 1 else ""
    normalized["phone_3"] = phones[2] if len(phones) > 2 else ""
    normalized["active_status"] = _normalize_work_manager_active_status(normalized.get("active_status", ""))
    normalized["current_employer"] = re.sub(r"\s+", " ", str(normalized.get("current_employer") or "").strip())
    normalized["current_workplace"] = re.sub(r"\s+", " ", str(normalized.get("current_workplace") or "").strip())
    normalized["details_url"] = str(normalized.get("details_url") or "").strip()
    normalized["project_manager_match"] = "true" if str(normalized.get("project_manager_match") or "").strip().lower() in {"1", "true", "yes", "כן"} else "false"
    normalized["project_manager_checked_at"] = str(normalized.get("project_manager_checked_at") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_marketing_construction_company_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in MARKETING_CONSTRUCTION_COMPANY_FIELDS}
    normalized["row_id"] = str(normalized.get("row_id") or uuid4()).strip()
    normalized["company_name"] = re.sub(r"\s+", " ", str(normalized.get("company_name") or "").strip())
    normalized["company_id"] = re.sub(r"\D+", "", str(normalized.get("company_id") or ""))
    normalized["phone"] = _normalize_work_manager_phone(normalized.get("phone", ""))
    normalized["address"] = re.sub(r"\s+", " ", str(normalized.get("address") or "").strip())
    normalized["email"] = _normalize_customer_emails(normalized.get("email", ""))
    normalized["details_url"] = str(normalized.get("details_url") or "").strip()
    normalized["notes"] = str(normalized.get("notes") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    if (
        normalized["notes"]
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", normalized["notes"])
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", normalized["updated_at"])
    ):
        normalized["notes"] = ""
    return normalized


def _normalize_finance_invoice_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in FINANCE_INVOICE_FIELDS}

    def _looks_like_datetime(value: str) -> bool:
        raw = str(value or "").strip()
        if not raw:
            return False
        try:
            parsedate_to_datetime(raw)
            return True
        except Exception:
            pass
        try:
            datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return True
        except Exception:
            return False

    normalized["row_id"] = str(normalized.get("row_id") or uuid4()).strip()
    if (
        str(normalized.get("source_file_name") or "").strip().count("/") == 2
        and str(normalized.get("total") or "").strip().startswith("/")
    ):
        legacy = dict(normalized)
        normalized["reference_number"] = ""
        normalized["allocation_number"] = ""
        normalized["service_or_product"] = str(legacy.get("reference_number") or "").strip()
        normalized["subtotal"] = str(legacy.get("allocation_number") or "").strip()
        normalized["vat"] = str(legacy.get("service_or_product") or "").strip()
        normalized["total"] = str(legacy.get("subtotal") or "").strip()
        normalized["source_file_name"] = str(legacy.get("vat") or "").strip()
        normalized["source_file_path"] = str(legacy.get("total") or "").strip()
        normalized["report_due_date"] = str(legacy.get("source_file_name") or "").strip()
        normalized["report_due_overrides"] = str(legacy.get("source_file_path") or "").strip()
        candidate_drive_id = str(legacy.get("report_due_date") or "").strip()
        candidate_drive_url = str(legacy.get("report_due_overrides") or "").strip()
        normalized["drive_file_id"] = candidate_drive_id if re.fullmatch(r"[A-Za-z0-9_-]{10,}", candidate_drive_id) else ""
        normalized["drive_url"] = candidate_drive_url if candidate_drive_url.startswith("http") else ""
        normalized["updated_at"] = str(legacy.get("drive_file_id") or legacy.get("updated_at") or "").strip()
    normalized["invoice_date"] = str(normalized.get("invoice_date") or "").strip()
    normalized["supplier_name"] = re.sub(r"\s+", " ", str(normalized.get("supplier_name") or "").strip())
    normalized["reference_number"] = str(normalized.get("reference_number") or "").strip()
    normalized["allocation_number"] = str(normalized.get("allocation_number") or "").strip()
    normalized["currency_code"] = str(normalized.get("currency_code") or "ILS").strip().upper() or "ILS"
    normalized["service_or_product"] = re.sub(r"\s+", " ", str(normalized.get("service_or_product") or "").strip())
    for amount_field in ("subtotal", "vat", "total"):
        raw = str(normalized.get(amount_field) or "").strip().replace(",", "")
        try:
            normalized[amount_field] = f"{float(raw):.2f}" if raw else ""
        except Exception:
            normalized[amount_field] = raw
    normalized["source_file_name"] = str(normalized.get("source_file_name") or "").strip()
    normalized["source_file_path"] = str(normalized.get("source_file_path") or "").strip()
    normalized["report_due_date"] = str(normalized.get("report_due_date") or "").strip()
    normalized["report_due_overrides"] = str(normalized.get("report_due_overrides") or "").strip()
    normalized["drive_file_id"] = str(normalized.get("drive_file_id") or "").strip()
    normalized["drive_url"] = str(normalized.get("drive_url") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    if _looks_like_datetime(normalized["report_due_date"]) and not normalized["updated_at"]:
        normalized["updated_at"] = normalized["report_due_date"]
        normalized["report_due_date"] = ""
    return normalized


def _normalize_finance_settings_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in FINANCE_SETTINGS_FIELDS}
    normalized["setting_key"] = str(normalized.get("setting_key") or "").strip()
    normalized["setting_value"] = str(normalized.get("setting_value") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_finance_customer_withholding_row(row: dict) -> dict:
    raw_row = row or {}
    normalized = {field: str(raw_row.get(field, "") or "") for field in FINANCE_CUSTOMER_WITHHOLDINGS_FIELDS}
    normalized["row_id"] = str(normalized.get("row_id") or uuid4()).strip()
    normalized["receipt_date"] = str(normalized.get("receipt_date") or "").strip()
    normalized["customer_name"] = re.sub(r"\s+", " ", str(normalized.get("customer_name") or "").strip())
    normalized["invoice_number"] = str(normalized.get("invoice_number") or "").strip()
    normalized["receipt_number"] = str(normalized.get("receipt_number") or "").strip()
    legacy_gross_amount = str(raw_row.get("withholding_applied") or "").strip()
    legacy_percent = str(raw_row.get("gross_amount") or "").strip()
    legacy_withheld = str(raw_row.get("withholding_percent") or "").strip()
    legacy_paid = str(raw_row.get("withheld_amount") or "").strip()
    legacy_mode = str(raw_row.get("paid_amount") or "").strip()
    legacy_updated_at = str(raw_row.get("source_mode") or "").strip()
    if (
        legacy_gross_amount
        and legacy_gross_amount.upper() not in {"TRUE", "FALSE"}
        and legacy_mode.upper() in {"PROD", "SB"}
        and re.match(r"^\d{4}-\d{2}-\d{2}T", legacy_updated_at)
    ):
        normalized["withholding_applied"] = "TRUE"
        normalized["gross_amount"] = legacy_gross_amount
        normalized["withholding_percent"] = legacy_percent
        normalized["withheld_amount"] = legacy_withheld
        normalized["paid_amount"] = legacy_paid
        normalized["source_mode"] = legacy_mode
        normalized["review_pending"] = ""
        normalized["migration_batch"] = ""
        normalized["updated_at"] = legacy_updated_at
    normalized["withholding_applied"] = "TRUE" if str(normalized.get("withholding_applied") or "").strip().upper() == "TRUE" else ""
    normalized["source_mode"] = _normalize_customer_source_mode(normalized.get("source_mode", ""))
    normalized["review_pending"] = "TRUE" if str(normalized.get("review_pending") or "").strip().upper() == "TRUE" else ""
    normalized["dismissed"] = "TRUE" if str(normalized.get("dismissed") or "").strip().upper() == "TRUE" else ""
    normalized["migration_batch"] = str(normalized.get("migration_batch") or "").strip()
    for amount_field in ("gross_amount", "withholding_percent", "withheld_amount", "paid_amount"):
        raw = str(normalized.get(amount_field) or "").strip().replace(",", "")
        try:
            normalized[amount_field] = f"{float(raw):.2f}" if raw else ""
        except Exception:
            normalized[amount_field] = raw
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _normalize_finance_bank_movement_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in FINANCE_BANK_MOVEMENTS_FIELDS}
    normalized["row_id"] = str(normalized.get("row_id") or uuid4()).strip()
    normalized["account_number"] = re.sub(r"\D+", "", str(normalized.get("account_number") or ""))
    normalized["account_name"] = re.sub(r"\s+", " ", str(normalized.get("account_name") or "").strip())
    normalized["company_name"] = re.sub(r"\s+", " ", str(normalized.get("company_name") or "").strip())
    normalized["section_name"] = re.sub(r"\s+", " ", str(normalized.get("section_name") or "").strip())
    normalized["transaction_date"] = str(normalized.get("transaction_date") or "").strip()
    normalized["value_date"] = str(normalized.get("value_date") or "").strip()
    normalized["description"] = re.sub(r"\s+", " ", str(normalized.get("description") or "").strip())
    normalized["operation_type"] = re.sub(r"\s+", " ", str(normalized.get("operation_type") or "").strip())
    for amount_field in ("amount", "balance"):
        raw = str(normalized.get(amount_field) or "").strip().replace(",", "")
        try:
            normalized[amount_field] = f"{float(raw):.2f}" if raw else ""
        except Exception:
            normalized[amount_field] = raw
    normalized["reference"] = str(normalized.get("reference") or "").strip()
    normalized["fee_or_notes"] = re.sub(r"\s+", " ", str(normalized.get("fee_or_notes") or "").strip())
    normalized["channel"] = re.sub(r"\s+", " ", str(normalized.get("channel") or "").strip())
    normalized["source_file_name"] = str(normalized.get("source_file_name") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _load_order_history_disk_cache() -> list[dict]:
    try:
        if not _ORDER_HISTORY_CACHE_FILE.exists():
            return []
        payload = json.loads(_ORDER_HISTORY_CACHE_FILE.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_order_history_row(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _load_quote_history_disk_cache() -> list[dict]:
    try:
        if not _QUOTE_HISTORY_CACHE_FILE.exists():
            return []
        payload = json.loads(_QUOTE_HISTORY_CACHE_FILE.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_quote_history_row(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _load_installation_cases_disk_cache() -> list[dict]:
    try:
        if not _INSTALLATION_CASES_CACHE_FILE.exists():
            return []
        payload = json.loads(_INSTALLATION_CASES_CACHE_FILE.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_installation_case_row(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _load_installation_visits_disk_cache() -> list[dict]:
    try:
        if not _INSTALLATION_VISITS_CACHE_FILE.exists():
            return []
        payload = json.loads(_INSTALLATION_VISITS_CACHE_FILE.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_installation_visit_row(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _load_pazomat_disk_cache() -> list[dict]:
    try:
        if not _PAZOMAT_CACHE_FILE.exists():
            return []
        payload = json.loads(_PAZOMAT_CACHE_FILE.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_pazomat_row(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _load_sibus_disk_cache() -> list[dict]:
    try:
        if not _SIBUS_CACHE_FILE.exists():
            return []
        payload = json.loads(_SIBUS_CACHE_FILE.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_sibus_row(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _load_supplier_delivery_note_disk_cache() -> list[dict]:
    try:
        if not _SUPPLIER_DELIVERY_NOTE_CACHE_FILE.exists():
            return []
        payload = json.loads(_SUPPLIER_DELIVERY_NOTE_CACHE_FILE.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_supplier_delivery_note_row(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _load_inventory_purchase_order_disk_cache() -> list[dict]:
    try:
        if not _INVENTORY_PURCHASE_ORDER_CACHE_FILE.exists():
            return []
        payload = json.loads(_INVENTORY_PURCHASE_ORDER_CACHE_FILE.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_inventory_purchase_order_row(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _load_working_order_disk_cache() -> list[dict]:
    try:
        if not _WORKING_ORDER_CACHE_FILE.exists():
            return []
        payload = json.loads(_WORKING_ORDER_CACHE_FILE.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_working_order_row(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _load_pricing_items_disk_cache() -> list[dict]:
    try:
        if not _PRICING_ITEMS_CACHE_FILE.exists():
            return []
        payload = json.loads(_PRICING_ITEMS_CACHE_FILE.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_pricing_item_row(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _load_pricing_components_disk_cache() -> list[dict]:
    try:
        if not _PRICING_COMPONENTS_CACHE_FILE.exists():
            return []
        payload = json.loads(_PRICING_COMPONENTS_CACHE_FILE.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_pricing_component_row(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _save_order_history_disk_cache(rows: list[dict]) -> None:
    try:
        _ORDER_HISTORY_CACHE_FILE.write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_order_history_row(row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _save_quote_history_disk_cache(rows: list[dict]) -> None:
    try:
        _QUOTE_HISTORY_CACHE_FILE.write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_quote_history_row(row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _save_installation_cases_disk_cache(rows: list[dict]) -> None:
    try:
        _INSTALLATION_CASES_CACHE_FILE.write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_installation_case_row(row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _save_installation_visits_disk_cache(rows: list[dict]) -> None:
    try:
        _INSTALLATION_VISITS_CACHE_FILE.write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_installation_visit_row(row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _save_pazomat_disk_cache(rows: list[dict]) -> None:
    try:
        _PAZOMAT_CACHE_FILE.write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_pazomat_row(row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _save_sibus_disk_cache(rows: list[dict]) -> None:
    try:
        _SIBUS_CACHE_FILE.write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_sibus_row(row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _save_supplier_delivery_note_disk_cache(rows: list[dict]) -> None:
    try:
        _SUPPLIER_DELIVERY_NOTE_CACHE_FILE.write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_supplier_delivery_note_row(row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _save_inventory_purchase_order_disk_cache(rows: list[dict]) -> None:
    try:
        _INVENTORY_PURCHASE_ORDER_CACHE_FILE.write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_inventory_purchase_order_row(row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _save_working_order_disk_cache(rows: list[dict]) -> None:
    try:
        _WORKING_ORDER_CACHE_FILE.write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_working_order_row(row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _save_pricing_items_disk_cache(rows: list[dict]) -> None:
    try:
        _PRICING_ITEMS_CACHE_FILE.write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_pricing_item_row(row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _save_pricing_components_disk_cache(rows: list[dict]) -> None:
    try:
        _PRICING_COMPONENTS_CACHE_FILE.write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_pricing_component_row(row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _load_customers_disk_cache(kind: str = "active") -> list[dict]:
    try:
        cache_file = _customer_cache_file(kind)
        if not cache_file.exists():
            return []
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_customer_row(row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _save_customers_disk_cache(rows: list[dict], kind: str = "active") -> None:
    try:
        _customer_cache_file(kind).write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_customer_row(row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def _normalize_marketing_row(kind: str, row: dict) -> dict:
    if kind == "finance_invoices":
        return _normalize_finance_invoice_row(row)
    if kind == "finance_settings":
        return _normalize_finance_settings_row(row)
    if kind == "finance_customer_withholdings":
        return _normalize_finance_customer_withholding_row(row)
    if kind == "finance_bank_movements":
        return _normalize_finance_bank_movement_row(row)
    if kind == "pipeline":
        return _normalize_marketing_pipeline_row(row)
    if kind == "work_managers":
        return _normalize_marketing_work_manager_row(row)
    if kind == "construction_companies":
        return _normalize_marketing_construction_company_row(row)
    if kind == "notes":
        return _normalize_marketing_note_row(row)
    if kind == "reminders":
        return _normalize_marketing_reminder_row(row)
    return _normalize_marketing_history_row(row)


def _marketing_cache_ref(kind: str):
    global _MARKETING_PIPELINE_ROWS_CACHE, _MARKETING_WORK_MANAGERS_ROWS_CACHE, _MARKETING_CONSTRUCTION_COMPANIES_ROWS_CACHE, _MARKETING_NOTES_ROWS_CACHE, _MARKETING_REMINDERS_ROWS_CACHE, _MARKETING_HISTORY_ROWS_CACHE, _FINANCE_INVOICE_ROWS_CACHE, _FINANCE_SETTINGS_ROWS_CACHE, _FINANCE_CUSTOMER_WITHHOLDINGS_ROWS_CACHE, _FINANCE_BANK_MOVEMENTS_ROWS_CACHE
    global _MARKETING_PIPELINE_ROWS_CACHE_TS, _MARKETING_WORK_MANAGERS_ROWS_CACHE_TS, _MARKETING_CONSTRUCTION_COMPANIES_ROWS_CACHE_TS, _MARKETING_NOTES_ROWS_CACHE_TS, _MARKETING_REMINDERS_ROWS_CACHE_TS, _MARKETING_HISTORY_ROWS_CACHE_TS, _FINANCE_INVOICE_ROWS_CACHE_TS, _FINANCE_SETTINGS_ROWS_CACHE_TS, _FINANCE_CUSTOMER_WITHHOLDINGS_ROWS_CACHE_TS, _FINANCE_BANK_MOVEMENTS_ROWS_CACHE_TS
    if kind == "finance_invoices":
        return "_FINANCE_INVOICE_ROWS_CACHE", "_FINANCE_INVOICE_ROWS_CACHE_TS"
    if kind == "finance_settings":
        return "_FINANCE_SETTINGS_ROWS_CACHE", "_FINANCE_SETTINGS_ROWS_CACHE_TS"
    if kind == "finance_customer_withholdings":
        return "_FINANCE_CUSTOMER_WITHHOLDINGS_ROWS_CACHE", "_FINANCE_CUSTOMER_WITHHOLDINGS_ROWS_CACHE_TS"
    if kind == "finance_bank_movements":
        return "_FINANCE_BANK_MOVEMENTS_ROWS_CACHE", "_FINANCE_BANK_MOVEMENTS_ROWS_CACHE_TS"
    if kind == "pipeline":
        return "_MARKETING_PIPELINE_ROWS_CACHE", "_MARKETING_PIPELINE_ROWS_CACHE_TS"
    if kind == "work_managers":
        return "_MARKETING_WORK_MANAGERS_ROWS_CACHE", "_MARKETING_WORK_MANAGERS_ROWS_CACHE_TS"
    if kind == "construction_companies":
        return "_MARKETING_CONSTRUCTION_COMPANIES_ROWS_CACHE", "_MARKETING_CONSTRUCTION_COMPANIES_ROWS_CACHE_TS"
    if kind == "notes":
        return "_MARKETING_NOTES_ROWS_CACHE", "_MARKETING_NOTES_ROWS_CACHE_TS"
    if kind == "reminders":
        return "_MARKETING_REMINDERS_ROWS_CACHE", "_MARKETING_REMINDERS_ROWS_CACHE_TS"
    return "_MARKETING_HISTORY_ROWS_CACHE", "_MARKETING_HISTORY_ROWS_CACHE_TS"


def _get_marketing_cache(kind: str) -> tuple[list[dict], float]:
    cache_name, ts_name = _marketing_cache_ref(kind)
    return globals()[cache_name], globals()[ts_name]


def _set_marketing_cache(kind: str, rows: list[dict]) -> None:
    cache_name, ts_name = _marketing_cache_ref(kind)
    globals()[cache_name] = [dict(row) for row in rows]
    globals()[ts_name] = time.time()


def _load_marketing_disk_cache(kind: str) -> list[dict]:
    try:
        cache_file = _marketing_cache_file(kind)
        if not cache_file.exists():
            return []
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            return []
        return [_normalize_marketing_row(kind, row) for row in rows if isinstance(row, dict)]
    except Exception:
        return []


def _save_marketing_disk_cache(kind: str, rows: list[dict]) -> None:
    try:
        _marketing_cache_file(kind).write_text(
            json.dumps(
                {
                    "saved_at": datetime.now().isoformat(timespec="seconds"),
                    "rows": [_normalize_marketing_row(kind, row) for row in (rows or [])],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass


def load_customer_rows(kind: str = "active") -> list[dict]:
    global _CUSTOMER_ROWS_CACHE, _CUSTOMER_ROWS_CACHE_TS, _INACTIVE_CUSTOMER_ROWS_CACHE, _INACTIVE_CUSTOMER_ROWS_CACHE_TS
    cache_rows = _INACTIVE_CUSTOMER_ROWS_CACHE if kind == "inactive" else _CUSTOMER_ROWS_CACHE
    cache_ts = _INACTIVE_CUSTOMER_ROWS_CACHE_TS if kind == "inactive" else _CUSTOMER_ROWS_CACHE_TS
    if cache_rows and (time.time() - cache_ts) <= _GENERIC_SHEET_CACHE_TTL_SECONDS:
        return [dict(row) for row in cache_rows]
    supabase_domain = "inactive_customers" if kind == "inactive" else "customers"
    if _supabase_enabled_for(supabase_domain):
        try:
            rows = [_normalize_customer_row(row) for row in supabase_store.fetch_domain_rows(supabase_domain)]
            rows = _dedupe_customer_rows(rows)
            if kind == "inactive":
                _INACTIVE_CUSTOMER_ROWS_CACHE = [dict(row) for row in rows]
                _INACTIVE_CUSTOMER_ROWS_CACHE_TS = time.time()
            else:
                _CUSTOMER_ROWS_CACHE = [dict(row) for row in rows]
                _CUSTOMER_ROWS_CACHE_TS = time.time()
            _save_customers_disk_cache(rows, kind)
            return rows
        except Exception:
            if cache_rows:
                return [dict(row) for row in cache_rows]
            disk_rows = _load_customers_disk_cache(kind)
            if disk_rows:
                return disk_rows
            raise
    service = _service()
    try:
        title, _ = _ensure_customers_sheet(service, kind)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if cache_rows:
                return [dict(row) for row in cache_rows]
            disk_rows = _load_customers_disk_cache(kind)
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:AR",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if cache_rows:
                return [dict(row) for row in cache_rows]
            disk_rows = _load_customers_disk_cache(kind)
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    rows: list[dict] = []
    for raw in values:
        padded = raw + [""] * max(0, len(CUSTOMER_FIELDS) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(CUSTOMER_FIELDS)}
        if any(str(value).strip() for value in row.values()):
            rows.append(_normalize_customer_row(row))
    rows = _dedupe_customer_rows(rows)
    if kind == "inactive":
        _INACTIVE_CUSTOMER_ROWS_CACHE = [dict(row) for row in rows]
        _INACTIVE_CUSTOMER_ROWS_CACHE_TS = time.time()
    else:
        _CUSTOMER_ROWS_CACHE = [dict(row) for row in rows]
        _CUSTOMER_ROWS_CACHE_TS = time.time()
    _save_customers_disk_cache(rows, kind)
    return rows


def save_customer_rows(rows: list[dict], kind: str = "active") -> dict:
    global _CUSTOMER_ROWS_CACHE, _CUSTOMER_ROWS_CACHE_TS, _INACTIVE_CUSTOMER_ROWS_CACHE, _INACTIVE_CUSTOMER_ROWS_CACHE_TS
    normalized_rows = _dedupe_customer_rows([_normalize_customer_row(row) for row in (rows or [])])
    cache_rows = _INACTIVE_CUSTOMER_ROWS_CACHE if kind == "inactive" else _CUSTOMER_ROWS_CACHE
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(cache_rows, ensure_ascii=False, sort_keys=True):
        sheet_name = "supabase:customers" if _supabase_enabled_for("inactive_customers" if kind == "inactive" else "customers") else kind
        return {"sheet": sheet_name, "rows_saved": len(normalized_rows), "skipped": True}
    supabase_domain = "inactive_customers" if kind == "inactive" else "customers"
    if _supabase_enabled_for(supabase_domain):
        result = supabase_store.replace_domain_rows(supabase_domain, normalized_rows)
        if kind == "inactive":
            _INACTIVE_CUSTOMER_ROWS_CACHE = [dict(row) for row in normalized_rows]
            _INACTIVE_CUSTOMER_ROWS_CACHE_TS = time.time()
        else:
            _CUSTOMER_ROWS_CACHE = [dict(row) for row in normalized_rows]
            _CUSTOMER_ROWS_CACHE_TS = time.time()
        _save_customers_disk_cache(normalized_rows, kind)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_customers_sheet(service, kind)

    values = [CUSTOMER_HEADERS] + [
        [row.get(field, "") for field in CUSTOMER_FIELDS]
        for row in normalized_rows
    ]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A2:AR",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    if kind == "inactive":
        _INACTIVE_CUSTOMER_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _INACTIVE_CUSTOMER_ROWS_CACHE_TS = time.time()
    else:
        _CUSTOMER_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _CUSTOMER_ROWS_CACHE_TS = time.time()
    _save_customers_disk_cache(normalized_rows, kind)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def get_cached_customer_rows(kind: str = "active") -> list[dict]:
    cache_rows = _INACTIVE_CUSTOMER_ROWS_CACHE if kind == "inactive" else _CUSTOMER_ROWS_CACHE
    if cache_rows:
        return [dict(row) for row in cache_rows]
    return _load_customers_disk_cache(kind)


def load_inactive_customer_rows() -> list[dict]:
    return load_customer_rows("inactive")


def save_inactive_customer_rows(rows: list[dict]) -> dict:
    return save_customer_rows(rows, "inactive")


def get_cached_inactive_customer_rows() -> list[dict]:
    return get_cached_customer_rows("inactive")


def load_order_history_rows(force_refresh: bool = False) -> list[dict]:
    global _ORDER_HISTORY_ROWS_CACHE, _ORDER_HISTORY_ROWS_CACHE_TS
    if (
        not force_refresh
        and _ORDER_HISTORY_ROWS_CACHE
        and (time.time() - _ORDER_HISTORY_ROWS_CACHE_TS) <= _GENERIC_SHEET_CACHE_TTL_SECONDS
    ):
        return [dict(row) for row in _ORDER_HISTORY_ROWS_CACHE]
    if _supabase_enabled_for("order_history"):
        try:
            rows = []
            for row in supabase_store.fetch_domain_rows("order_history"):
                normalized = _normalize_order_history_row(row)
                if _is_broken_order_history_row(normalized):
                    continue
                rows.append(normalized)
            rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
            _ORDER_HISTORY_ROWS_CACHE = [dict(row) for row in rows]
            _ORDER_HISTORY_ROWS_CACHE_TS = time.time()
            _save_order_history_disk_cache(rows)
            return rows
        except Exception:
            if _ORDER_HISTORY_ROWS_CACHE:
                return [dict(row) for row in _ORDER_HISTORY_ROWS_CACHE]
            disk_rows = _load_order_history_disk_cache()
            if disk_rows:
                return disk_rows
            raise
    service = _service()
    try:
        title, _ = _ensure_order_history_sheet(service)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if _ORDER_HISTORY_ROWS_CACHE:
                return [dict(row) for row in _ORDER_HISTORY_ROWS_CACHE]
            disk_rows = _load_order_history_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:AQ",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if _ORDER_HISTORY_ROWS_CACHE:
                return [dict(row) for row in _ORDER_HISTORY_ROWS_CACHE]
            disk_rows = _load_order_history_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    rows: list[dict] = []
    for raw in values:
        padded = raw + [""] * max(0, len(ORDER_HISTORY_FIELDS) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(ORDER_HISTORY_FIELDS)}
        if any(str(value).strip() for value in row.values()):
            normalized = _normalize_order_history_row(row)
            if _is_broken_order_history_row(normalized):
                continue
            rows.append(normalized)
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    _ORDER_HISTORY_ROWS_CACHE = [dict(row) for row in rows]
    _ORDER_HISTORY_ROWS_CACHE_TS = time.time()
    _save_order_history_disk_cache(rows)
    return rows


def load_quote_history_rows(force_refresh: bool = False) -> list[dict]:
    global _QUOTE_HISTORY_ROWS_CACHE, _QUOTE_HISTORY_ROWS_CACHE_TS
    if (
        not force_refresh
        and _QUOTE_HISTORY_ROWS_CACHE
        and (time.time() - _QUOTE_HISTORY_ROWS_CACHE_TS) <= _GENERIC_SHEET_CACHE_TTL_SECONDS
    ):
        return [dict(row) for row in _QUOTE_HISTORY_ROWS_CACHE]
    if _supabase_enabled_for("quote_history"):
        try:
            rows = [_normalize_quote_history_row(row) for row in supabase_store.fetch_domain_rows("quote_history")]
            rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
            _QUOTE_HISTORY_ROWS_CACHE = [dict(row) for row in rows]
            _QUOTE_HISTORY_ROWS_CACHE_TS = time.time()
            _save_quote_history_disk_cache(rows)
            return rows
        except Exception:
            if _QUOTE_HISTORY_ROWS_CACHE:
                return [dict(row) for row in _QUOTE_HISTORY_ROWS_CACHE]
            disk_rows = _load_quote_history_disk_cache()
            if disk_rows:
                return disk_rows
            raise
    service = _service()
    try:
        title, _ = _ensure_quote_history_sheet(service)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if _QUOTE_HISTORY_ROWS_CACHE:
                return [dict(row) for row in _QUOTE_HISTORY_ROWS_CACHE]
            disk_rows = _load_quote_history_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            ranges=[f"{title}!A2:AG"],
            includeGridData=True,
            fields="sheets(data(rowData(values(formattedValue,effectiveValue,userEnteredValue))))",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if _QUOTE_HISTORY_ROWS_CACHE:
                return [dict(row) for row in _QUOTE_HISTORY_ROWS_CACHE]
            disk_rows = _load_quote_history_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    sheet_data = (((result.get("sheets") or [{}])[0].get("data") or [{}])[0].get("rowData") or [])
    values: list[list[str]] = []
    for row_data in sheet_data:
        cells = row_data.get("values") or []
        raw_row: list[str] = []
        for index in range(len(QUOTE_HISTORY_FIELDS)):
            cell = cells[index] if index < len(cells) else {}
            value = ""
            if isinstance(cell, dict):
                if "formattedValue" in cell:
                    value = str(cell.get("formattedValue") or "")
                else:
                    source = (cell.get("userEnteredValue") or {}) or (cell.get("effectiveValue") or {})
                    value = str(
                        source.get("stringValue")
                        or source.get("numberValue")
                        or source.get("boolValue")
                        or ""
                    )
            raw_row.append(value)
        if any(str(value).strip() for value in raw_row):
            values.append(raw_row)
    rows: list[dict] = []
    for raw in values:
        row = {field: str(raw[index] or "") for index, field in enumerate(QUOTE_HISTORY_FIELDS)}
        if any(str(value).strip() for value in row.values()):
            rows.append(_normalize_quote_history_row(row))
    cached_rows = get_cached_quote_history_rows()
    if cached_rows:
        merged_rows: dict[str, dict] = {}
        for row in rows:
            history_id = str(row.get("history_id") or "").strip()
            if history_id:
                merged_rows[history_id] = row
        for row in cached_rows:
            normalized_row = _normalize_quote_history_row(row)
            history_id = str(normalized_row.get("history_id") or "").strip()
            if history_id:
                merged_rows[history_id] = normalized_row
        if merged_rows:
            rows = list(merged_rows.values())
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    _QUOTE_HISTORY_ROWS_CACHE = [dict(row) for row in rows]
    _QUOTE_HISTORY_ROWS_CACHE_TS = time.time()
    _save_quote_history_disk_cache(rows)
    return rows


def load_installation_case_rows(force_refresh: bool = False) -> list[dict]:
    global _INSTALLATION_CASE_ROWS_CACHE, _INSTALLATION_CASE_ROWS_CACHE_TS
    if (
        not force_refresh
        and _INSTALLATION_CASE_ROWS_CACHE
        and (time.time() - _INSTALLATION_CASE_ROWS_CACHE_TS) <= _GENERIC_SHEET_CACHE_TTL_SECONDS
    ):
        return [dict(row) for row in _INSTALLATION_CASE_ROWS_CACHE]
    service = _service()
    try:
        title, _ = _ensure_installations_sheet(service, "cases")
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if _INSTALLATION_CASE_ROWS_CACHE:
                return [dict(row) for row in _INSTALLATION_CASE_ROWS_CACHE]
            disk_rows = _load_installation_cases_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:AZ",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if _INSTALLATION_CASE_ROWS_CACHE:
                return [dict(row) for row in _INSTALLATION_CASE_ROWS_CACHE]
            disk_rows = _load_installation_cases_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    rows: list[dict] = []
    for raw in values:
        padded = raw + [""] * max(0, len(INSTALLATION_CASE_FIELDS) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(INSTALLATION_CASE_FIELDS)}
        if any(str(value).strip() for value in row.values()):
            rows.append(_normalize_installation_case_row(row))
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    _INSTALLATION_CASE_ROWS_CACHE = [dict(row) for row in rows]
    _INSTALLATION_CASE_ROWS_CACHE_TS = time.time()
    _save_installation_cases_disk_cache(rows)
    return rows


def load_installation_visit_rows(force_refresh: bool = False) -> list[dict]:
    global _INSTALLATION_VISIT_ROWS_CACHE, _INSTALLATION_VISIT_ROWS_CACHE_TS
    if (
        not force_refresh
        and _INSTALLATION_VISIT_ROWS_CACHE
        and (time.time() - _INSTALLATION_VISIT_ROWS_CACHE_TS) <= _GENERIC_SHEET_CACHE_TTL_SECONDS
    ):
        return [dict(row) for row in _INSTALLATION_VISIT_ROWS_CACHE]
    service = _service()
    try:
        title, _ = _ensure_installations_sheet(service, "visits")
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if _INSTALLATION_VISIT_ROWS_CACHE:
                return [dict(row) for row in _INSTALLATION_VISIT_ROWS_CACHE]
            disk_rows = _load_installation_visits_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:AZ",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if _INSTALLATION_VISIT_ROWS_CACHE:
                return [dict(row) for row in _INSTALLATION_VISIT_ROWS_CACHE]
            disk_rows = _load_installation_visits_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    rows: list[dict] = []
    for raw in values:
        padded = raw + [""] * max(0, len(INSTALLATION_VISIT_FIELDS) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(INSTALLATION_VISIT_FIELDS)}
        if any(str(value).strip() for value in row.values()):
            rows.append(_normalize_installation_visit_row(row))
    rows.sort(key=lambda row: (str(row.get("visit_date") or ""), str(row.get("created_at") or "")), reverse=True)
    _INSTALLATION_VISIT_ROWS_CACHE = [dict(row) for row in rows]
    _INSTALLATION_VISIT_ROWS_CACHE_TS = time.time()
    _save_installation_visits_disk_cache(rows)
    return rows


def load_pazomat_rows(force_refresh: bool = False) -> list[dict]:
    global _PAZOMAT_ROWS_CACHE, _PAZOMAT_ROWS_CACHE_TS
    if (
        not force_refresh
        and _PAZOMAT_ROWS_CACHE
        and (time.time() - _PAZOMAT_ROWS_CACHE_TS) <= _GENERIC_SHEET_CACHE_TTL_SECONDS
    ):
        return [dict(row) for row in _PAZOMAT_ROWS_CACHE]
    if _supabase_enabled_for("pazomat"):
        try:
            rows = [_normalize_pazomat_row(row) for row in supabase_store.fetch_domain_rows("pazomat")]
            rows.sort(key=_pazomat_sort_key)
            _PAZOMAT_ROWS_CACHE = [dict(row) for row in rows]
            _PAZOMAT_ROWS_CACHE_TS = time.time()
            _save_pazomat_disk_cache(rows)
            return rows
        except Exception:
            if _PAZOMAT_ROWS_CACHE:
                return [dict(row) for row in _PAZOMAT_ROWS_CACHE]
            disk_rows = _load_pazomat_disk_cache()
            if disk_rows:
                return disk_rows
            raise
    service = _service()
    try:
        title, _ = _ensure_pazomat_sheet(service)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if _PAZOMAT_ROWS_CACHE:
                return [dict(row) for row in _PAZOMAT_ROWS_CACHE]
            disk_rows = _load_pazomat_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:W",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if _PAZOMAT_ROWS_CACHE:
                return [dict(row) for row in _PAZOMAT_ROWS_CACHE]
            disk_rows = _load_pazomat_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    rows: list[dict] = []
    for raw in values:
        padded = raw + [""] * max(0, len(PAZOMAT_FIELDS) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(PAZOMAT_FIELDS)}
        if any(str(value).strip() for value in row.values()):
            rows.append(_normalize_pazomat_row(row))
    rows.sort(key=_pazomat_sort_key)
    _PAZOMAT_ROWS_CACHE = [dict(row) for row in rows]
    _PAZOMAT_ROWS_CACHE_TS = time.time()
    _save_pazomat_disk_cache(rows)
    return rows


def load_sibus_rows(force_refresh: bool = False) -> list[dict]:
    global _SIBUS_ROWS_CACHE, _SIBUS_ROWS_CACHE_TS
    if (
        not force_refresh
        and _SIBUS_ROWS_CACHE
        and (time.time() - _SIBUS_ROWS_CACHE_TS) <= _GENERIC_SHEET_CACHE_TTL_SECONDS
    ):
        return [dict(row) for row in _SIBUS_ROWS_CACHE]
    if _supabase_enabled_for("sibus"):
        try:
            rows = [_normalize_sibus_row(row) for row in supabase_store.fetch_domain_rows("sibus")]
            rows.sort(key=_sibus_sort_key)
            _SIBUS_ROWS_CACHE = [dict(row) for row in rows]
            _SIBUS_ROWS_CACHE_TS = time.time()
            _save_sibus_disk_cache(rows)
            return rows
        except Exception:
            if _SIBUS_ROWS_CACHE:
                return [dict(row) for row in _SIBUS_ROWS_CACHE]
            disk_rows = _load_sibus_disk_cache()
            if disk_rows:
                return disk_rows
            raise
    service = _service()
    try:
        title, _ = _ensure_sibus_sheet(service)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if _SIBUS_ROWS_CACHE:
                return [dict(row) for row in _SIBUS_ROWS_CACHE]
            disk_rows = _load_sibus_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:T",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if _SIBUS_ROWS_CACHE:
                return [dict(row) for row in _SIBUS_ROWS_CACHE]
            disk_rows = _load_sibus_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    rows: list[dict] = []
    for raw in values:
        padded = raw + [""] * max(0, len(SIBUS_FIELDS) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(SIBUS_FIELDS)}
        if any(str(value).strip() for value in row.values()):
            rows.append(_normalize_sibus_row(row))
    rows.sort(key=_sibus_sort_key)
    _SIBUS_ROWS_CACHE = [dict(row) for row in rows]
    _SIBUS_ROWS_CACHE_TS = time.time()
    _save_sibus_disk_cache(rows)
    return rows


def load_supplier_delivery_note_rows(force_refresh: bool = False) -> list[dict]:
    global _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE, _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE_TS
    if (
        not force_refresh
        and _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE
        and (time.time() - _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE_TS) <= _GENERIC_SHEET_CACHE_TTL_SECONDS
    ):
        return [dict(row) for row in _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE]
    if _supabase_enabled_for("supplier_delivery_notes"):
        try:
            rows = [_normalize_supplier_delivery_note_row(row) for row in supabase_store.fetch_domain_rows("supplier_delivery_notes")]
            rows.sort(
                key=lambda row: (
                    str(row.get("delivery_date") or ""),
                    str(row.get("delivery_note_number") or ""),
                    str(row.get("item_index") or ""),
                ),
                reverse=True,
            )
            _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE = [dict(row) for row in rows]
            _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE_TS = time.time()
            _save_supplier_delivery_note_disk_cache(rows)
            return rows
        except Exception:
            if _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE:
                return [dict(row) for row in _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE]
            disk_rows = _load_supplier_delivery_note_disk_cache()
            if disk_rows:
                return disk_rows
            raise
    service = _service()
    try:
        title, _ = _ensure_supplier_delivery_note_sheet(service)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE:
                return [dict(row) for row in _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE]
            disk_rows = _load_supplier_delivery_note_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:Z",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE:
                return [dict(row) for row in _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE]
            disk_rows = _load_supplier_delivery_note_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    rows: list[dict] = []
    for raw in values:
        padded = raw + [""] * max(0, len(SUPPLIER_DELIVERY_NOTE_FIELDS) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(SUPPLIER_DELIVERY_NOTE_FIELDS)}
        if any(str(value).strip() for value in row.values()):
            rows.append(_normalize_supplier_delivery_note_row(row))
    rows.sort(
        key=lambda row: (
            str(row.get("delivery_date") or ""),
            str(row.get("delivery_note_number") or ""),
            str(row.get("item_index") or ""),
        ),
        reverse=True,
    )
    _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE = [dict(row) for row in rows]
    _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE_TS = time.time()
    _save_supplier_delivery_note_disk_cache(rows)
    return rows


def load_inventory_purchase_order_rows(force_refresh: bool = False) -> list[dict]:
    global _INVENTORY_PURCHASE_ORDER_ROWS_CACHE, _INVENTORY_PURCHASE_ORDER_ROWS_CACHE_TS
    if (
        not force_refresh
        and _INVENTORY_PURCHASE_ORDER_ROWS_CACHE
        and (time.time() - _INVENTORY_PURCHASE_ORDER_ROWS_CACHE_TS) <= _GENERIC_SHEET_CACHE_TTL_SECONDS
    ):
        return [dict(row) for row in _INVENTORY_PURCHASE_ORDER_ROWS_CACHE]
    if _supabase_enabled_for("inventory_purchase_orders"):
        try:
            rows = [_normalize_inventory_purchase_order_row(row) for row in supabase_store.fetch_domain_rows("inventory_purchase_orders")]
            rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
            _INVENTORY_PURCHASE_ORDER_ROWS_CACHE = [dict(row) for row in rows]
            _INVENTORY_PURCHASE_ORDER_ROWS_CACHE_TS = time.time()
            _save_inventory_purchase_order_disk_cache(rows)
            return rows
        except Exception:
            if _INVENTORY_PURCHASE_ORDER_ROWS_CACHE:
                return [dict(row) for row in _INVENTORY_PURCHASE_ORDER_ROWS_CACHE]
            disk_rows = _load_inventory_purchase_order_disk_cache()
            if disk_rows:
                return disk_rows
            raise
    service = _service()
    try:
        title, _ = _ensure_inventory_purchase_orders_sheet(service)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if _INVENTORY_PURCHASE_ORDER_ROWS_CACHE:
                return [dict(row) for row in _INVENTORY_PURCHASE_ORDER_ROWS_CACHE]
            disk_rows = _load_inventory_purchase_order_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:AA",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if _INVENTORY_PURCHASE_ORDER_ROWS_CACHE:
                return [dict(row) for row in _INVENTORY_PURCHASE_ORDER_ROWS_CACHE]
            disk_rows = _load_inventory_purchase_order_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    rows: list[dict] = []
    for raw in values:
        padded = raw + [""] * max(0, len(INVENTORY_PURCHASE_ORDER_FIELDS) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(INVENTORY_PURCHASE_ORDER_FIELDS)}
        if any(str(value).strip() for value in row.values()):
            rows.append(_normalize_inventory_purchase_order_row(row))
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    _INVENTORY_PURCHASE_ORDER_ROWS_CACHE = [dict(row) for row in rows]
    _INVENTORY_PURCHASE_ORDER_ROWS_CACHE_TS = time.time()
    _save_inventory_purchase_order_disk_cache(rows)
    return rows


def get_cached_working_order_rows() -> list[dict]:
    global _WORKING_ORDER_ROWS_CACHE, _WORKING_ORDER_ROWS_CACHE_TS
    if _WORKING_ORDER_ROWS_CACHE:
        return [dict(row) for row in _WORKING_ORDER_ROWS_CACHE]
    disk_rows = _load_working_order_disk_cache()
    if disk_rows:
        _WORKING_ORDER_ROWS_CACHE = [dict(row) for row in disk_rows]
        _WORKING_ORDER_ROWS_CACHE_TS = time.time()
        return [dict(row) for row in _WORKING_ORDER_ROWS_CACHE]
    return []


def load_working_order_rows(force_refresh: bool = False) -> list[dict]:
    global _WORKING_ORDER_ROWS_CACHE, _WORKING_ORDER_ROWS_CACHE_TS
    if (
        not force_refresh
        and _WORKING_ORDER_ROWS_CACHE
        and (time.time() - _WORKING_ORDER_ROWS_CACHE_TS) <= _GENERIC_SHEET_CACHE_TTL_SECONDS
    ):
        return [dict(row) for row in _WORKING_ORDER_ROWS_CACHE]
    if _supabase_enabled_for("working_orders"):
        try:
            rows = [_normalize_working_order_row(row) for row in supabase_store.fetch_domain_rows("working_orders")]
            rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
            _WORKING_ORDER_ROWS_CACHE = [dict(row) for row in rows]
            _WORKING_ORDER_ROWS_CACHE_TS = time.time()
            _save_working_order_disk_cache(rows)
            return rows
        except Exception:
            if _WORKING_ORDER_ROWS_CACHE:
                return [dict(row) for row in _WORKING_ORDER_ROWS_CACHE]
            disk_rows = _load_working_order_disk_cache()
            if disk_rows:
                return disk_rows
            raise
    service = _service()
    try:
        title, _ = _ensure_working_orders_sheet(service)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if _WORKING_ORDER_ROWS_CACHE:
                return [dict(row) for row in _WORKING_ORDER_ROWS_CACHE]
            disk_rows = _load_working_order_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:AK",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if _WORKING_ORDER_ROWS_CACHE:
                return [dict(row) for row in _WORKING_ORDER_ROWS_CACHE]
            disk_rows = _load_working_order_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    rows: list[dict] = []
    for raw in values:
        padded = raw + [""] * max(0, len(WORKING_ORDER_FIELDS) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(WORKING_ORDER_FIELDS)}
        if any(str(value).strip() for value in row.values()):
            rows.append(_normalize_working_order_row(row))
    rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    _WORKING_ORDER_ROWS_CACHE = [dict(row) for row in rows]
    _WORKING_ORDER_ROWS_CACHE_TS = time.time()
    _save_working_order_disk_cache(rows)
    return rows


def load_pricing_rows(kind: str, force_refresh: bool = False) -> list[dict]:
    global _PRICING_ITEM_ROWS_CACHE, _PRICING_ITEM_ROWS_CACHE_TS, _PRICING_COMPONENT_ROWS_CACHE, _PRICING_COMPONENT_ROWS_CACHE_TS
    cache_rows = _PRICING_COMPONENT_ROWS_CACHE if kind == "components" else _PRICING_ITEM_ROWS_CACHE
    cache_ts = _PRICING_COMPONENT_ROWS_CACHE_TS if kind == "components" else _PRICING_ITEM_ROWS_CACHE_TS
    disk_loader = _load_pricing_components_disk_cache if kind == "components" else _load_pricing_items_disk_cache
    normalizer = _normalize_pricing_component_row if kind == "components" else _normalize_pricing_item_row
    fields = PRICING_COMPONENT_FIELDS if kind == "components" else PRICING_ITEM_FIELDS
    sort_key = (
        (lambda row: (str(row.get("item_id") or ""), int(str(row.get("line_order") or "0") or 0), str(row.get("component_id") or "")))
        if kind == "components"
        else (lambda row: (str(row.get("kind") or ""), str(row.get("name") or "")))
    )

    if not force_refresh and cache_rows and (time.time() - cache_ts) <= _GENERIC_SHEET_CACHE_TTL_SECONDS:
        return [dict(row) for row in cache_rows]

    supabase_domain = _supabase_domain_for_pricing_kind(kind)
    if supabase_domain and _supabase_enabled_for(supabase_domain):
        try:
            rows = [normalizer(row) for row in supabase_store.fetch_domain_rows(supabase_domain)]
            rows.sort(key=sort_key)
            if kind == "components":
                _PRICING_COMPONENT_ROWS_CACHE = [dict(row) for row in rows]
                _PRICING_COMPONENT_ROWS_CACHE_TS = time.time()
                _save_pricing_components_disk_cache(rows)
            else:
                _PRICING_ITEM_ROWS_CACHE = [dict(row) for row in rows]
                _PRICING_ITEM_ROWS_CACHE_TS = time.time()
                _save_pricing_items_disk_cache(rows)
            return rows
        except Exception:
            if cache_rows:
                return [dict(row) for row in cache_rows]
            disk_rows = disk_loader()
            if disk_rows:
                return disk_rows
            raise

    service = _service()
    try:
        title, _ = _ensure_pricing_sheet(service, kind)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if cache_rows:
                return [dict(row) for row in cache_rows]
            disk_rows = disk_loader()
            if disk_rows:
                return disk_rows
        raise
    try:
        end_column = "T" if kind == "components" else "O"
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:{end_column}",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if cache_rows:
                return [dict(row) for row in cache_rows]
            disk_rows = disk_loader()
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    rows: list[dict] = []
    for raw in values:
        padded = raw + [""] * max(0, len(fields) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(fields)}
        if any(str(value).strip() for value in row.values()):
            rows.append(normalizer(row))
    rows.sort(key=sort_key)
    if kind == "components":
        _PRICING_COMPONENT_ROWS_CACHE = [dict(row) for row in rows]
        _PRICING_COMPONENT_ROWS_CACHE_TS = time.time()
        _save_pricing_components_disk_cache(rows)
    else:
        _PRICING_ITEM_ROWS_CACHE = [dict(row) for row in rows]
        _PRICING_ITEM_ROWS_CACHE_TS = time.time()
        _save_pricing_items_disk_cache(rows)
    return rows


def save_order_history_rows(rows: list[dict]) -> dict:
    global _ORDER_HISTORY_ROWS_CACHE, _ORDER_HISTORY_ROWS_CACHE_TS
    normalized_rows = [_normalize_order_history_row(row) for row in (rows or [])]
    normalized_rows = [row for row in normalized_rows if not _is_broken_order_history_row(row)]
    normalized_rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(_ORDER_HISTORY_ROWS_CACHE, ensure_ascii=False, sort_keys=True):
        return {"sheet": "supabase:order_history" if _supabase_enabled_for("order_history") else settings.google_sheets_order_history_tab, "rows_saved": len(normalized_rows), "skipped": True}
    if _supabase_enabled_for("order_history"):
        result = supabase_store.replace_domain_rows("order_history", normalized_rows)
        _ORDER_HISTORY_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _ORDER_HISTORY_ROWS_CACHE_TS = time.time()
        _save_order_history_disk_cache(normalized_rows)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_order_history_sheet(service)

    values = [ORDER_HISTORY_HEADERS] + [
        [row.get(field, "") for field in ORDER_HISTORY_FIELDS]
        for row in normalized_rows
    ]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A2:AQ",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _ORDER_HISTORY_ROWS_CACHE = [dict(row) for row in normalized_rows]
    _ORDER_HISTORY_ROWS_CACHE_TS = time.time()
    _save_order_history_disk_cache(normalized_rows)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def save_quote_history_rows(rows: list[dict]) -> dict:
    global _QUOTE_HISTORY_ROWS_CACHE, _QUOTE_HISTORY_ROWS_CACHE_TS
    normalized_rows = [_normalize_quote_history_row(row) for row in (rows or [])]
    normalized_rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(_QUOTE_HISTORY_ROWS_CACHE, ensure_ascii=False, sort_keys=True):
        return {"sheet": "supabase:quote_history" if _supabase_enabled_for("quote_history") else settings.google_sheets_quote_history_tab, "rows_saved": len(normalized_rows), "skipped": True}
    if _supabase_enabled_for("quote_history"):
        result = supabase_store.replace_domain_rows("quote_history", normalized_rows)
        _QUOTE_HISTORY_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _QUOTE_HISTORY_ROWS_CACHE_TS = time.time()
        _save_quote_history_disk_cache(normalized_rows)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, sheet_id = _ensure_quote_history_sheet(service)

    values = [QUOTE_HISTORY_HEADERS] + [
        [row.get(field, "") for field in QUOTE_HISTORY_FIELDS]
        for row in normalized_rows
    ]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1:AJ",
        body={},
    ).execute()
    rows_data = []
    for row in values:
        cell_values = []
        for value in row:
            text = str(value or "")
            cell_values.append({"userEnteredValue": {"stringValue": text}} if text else {})
        rows_data.append({"values": cell_values})
    service.spreadsheets().batchUpdate(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        body={
            "requests": [
                {
                    "updateCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": 0,
                            "endRowIndex": len(rows_data),
                            "startColumnIndex": 0,
                            "endColumnIndex": len(QUOTE_HISTORY_FIELDS),
                        },
                        "rows": rows_data,
                        "fields": "userEnteredValue",
                    }
                }
            ]
        },
    ).execute()
    _QUOTE_HISTORY_ROWS_CACHE = [dict(row) for row in normalized_rows]
    _QUOTE_HISTORY_ROWS_CACHE_TS = time.time()
    _save_quote_history_disk_cache(normalized_rows)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def save_installation_case_rows(rows: list[dict]) -> dict:
    global _INSTALLATION_CASE_ROWS_CACHE, _INSTALLATION_CASE_ROWS_CACHE_TS
    normalized_rows = [_normalize_installation_case_row(row) for row in (rows or [])]
    normalized_rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(
        _INSTALLATION_CASE_ROWS_CACHE, ensure_ascii=False, sort_keys=True
    ):
        return {"sheet": settings.google_sheets_installation_cases_tab, "rows_saved": len(normalized_rows), "skipped": True}

    service = _service()
    title, _ = _ensure_installations_sheet(service, "cases")
    values = [INSTALLATION_CASE_HEADERS] + [
        [row.get(field, "") for field in INSTALLATION_CASE_FIELDS]
        for row in normalized_rows
    ]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1:AZ",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _INSTALLATION_CASE_ROWS_CACHE = [dict(row) for row in normalized_rows]
    _INSTALLATION_CASE_ROWS_CACHE_TS = time.time()
    _save_installation_cases_disk_cache(normalized_rows)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def save_installation_visit_rows(rows: list[dict]) -> dict:
    global _INSTALLATION_VISIT_ROWS_CACHE, _INSTALLATION_VISIT_ROWS_CACHE_TS
    normalized_rows = [_normalize_installation_visit_row(row) for row in (rows or [])]
    normalized_rows.sort(key=lambda row: (str(row.get("visit_date") or ""), str(row.get("created_at") or "")), reverse=True)
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(
        _INSTALLATION_VISIT_ROWS_CACHE, ensure_ascii=False, sort_keys=True
    ):
        return {"sheet": settings.google_sheets_installation_visits_tab, "rows_saved": len(normalized_rows), "skipped": True}

    service = _service()
    title, _ = _ensure_installations_sheet(service, "visits")
    values = [INSTALLATION_VISIT_HEADERS] + [
        [row.get(field, "") for field in INSTALLATION_VISIT_FIELDS]
        for row in normalized_rows
    ]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1:AZ",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _INSTALLATION_VISIT_ROWS_CACHE = [dict(row) for row in normalized_rows]
    _INSTALLATION_VISIT_ROWS_CACHE_TS = time.time()
    _save_installation_visits_disk_cache(normalized_rows)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def save_pazomat_rows(rows: list[dict]) -> dict:
    global _PAZOMAT_ROWS_CACHE, _PAZOMAT_ROWS_CACHE_TS
    normalized_rows = [_normalize_pazomat_row(row) for row in (rows or [])]
    normalized_rows.sort(key=_pazomat_sort_key)
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(
        _PAZOMAT_ROWS_CACHE, ensure_ascii=False, sort_keys=True
    ):
        return {
            "sheet": "supabase:pazomat" if _supabase_enabled_for("pazomat") else settings.google_sheets_pazomat_tab,
            "rows_saved": len(normalized_rows),
            "skipped": True,
        }
    if _supabase_enabled_for("pazomat"):
        result = supabase_store.replace_domain_rows("pazomat", normalized_rows)
        _PAZOMAT_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _PAZOMAT_ROWS_CACHE_TS = time.time()
        _save_pazomat_disk_cache(normalized_rows)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_pazomat_sheet(service)
    values = [PAZOMAT_HEADERS] + [[row.get(field, "") for field in PAZOMAT_FIELDS] for row in normalized_rows]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1:W",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _PAZOMAT_ROWS_CACHE = [dict(row) for row in normalized_rows]
    _PAZOMAT_ROWS_CACHE_TS = time.time()
    _save_pazomat_disk_cache(normalized_rows)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def save_sibus_rows(rows: list[dict]) -> dict:
    global _SIBUS_ROWS_CACHE, _SIBUS_ROWS_CACHE_TS
    normalized_rows = [_normalize_sibus_row(row) for row in (rows or [])]
    normalized_rows.sort(key=_sibus_sort_key)
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(
        _SIBUS_ROWS_CACHE, ensure_ascii=False, sort_keys=True
    ):
        return {
            "sheet": "supabase:sibus" if _supabase_enabled_for("sibus") else settings.google_sheets_sibus_tab,
            "rows_saved": len(normalized_rows),
            "skipped": True,
        }
    if _supabase_enabled_for("sibus"):
        result = supabase_store.replace_domain_rows("sibus", normalized_rows)
        _SIBUS_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _SIBUS_ROWS_CACHE_TS = time.time()
        _save_sibus_disk_cache(normalized_rows)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_sibus_sheet(service)
    values = [SIBUS_HEADERS] + [[row.get(field, "") for field in SIBUS_FIELDS] for row in normalized_rows]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1:T",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _SIBUS_ROWS_CACHE = [dict(row) for row in normalized_rows]
    _SIBUS_ROWS_CACHE_TS = time.time()
    _save_sibus_disk_cache(normalized_rows)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def save_supplier_delivery_note_rows(rows: list[dict]) -> dict:
    global _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE, _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE_TS
    normalized_rows = [_normalize_supplier_delivery_note_row(row) for row in (rows or [])]
    normalized_rows.sort(
        key=lambda row: (
            str(row.get("delivery_date") or ""),
            str(row.get("delivery_note_number") or ""),
            str(row.get("item_index") or ""),
        ),
        reverse=True,
    )
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(
        _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE, ensure_ascii=False, sort_keys=True
    ):
        return {
            "sheet": "supabase:supplier_delivery_notes" if _supabase_enabled_for("supplier_delivery_notes") else settings.google_sheets_supplier_delivery_note_tab,
            "rows_saved": len(normalized_rows),
            "skipped": True,
        }
    if _supabase_enabled_for("supplier_delivery_notes"):
        result = supabase_store.replace_domain_rows("supplier_delivery_notes", normalized_rows)
        _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE_TS = time.time()
        _save_supplier_delivery_note_disk_cache(normalized_rows)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_supplier_delivery_note_sheet(service)
    values = [SUPPLIER_DELIVERY_NOTE_HEADERS] + [
        [row.get(field, "") for field in SUPPLIER_DELIVERY_NOTE_FIELDS]
        for row in normalized_rows
    ]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1:Z",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE = [dict(row) for row in normalized_rows]
    _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE_TS = time.time()
    _save_supplier_delivery_note_disk_cache(normalized_rows)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def save_inventory_purchase_order_rows(rows: list[dict]) -> dict:
    global _INVENTORY_PURCHASE_ORDER_ROWS_CACHE, _INVENTORY_PURCHASE_ORDER_ROWS_CACHE_TS
    normalized_rows = [_normalize_inventory_purchase_order_row(row) for row in (rows or [])]
    normalized_rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(
        _INVENTORY_PURCHASE_ORDER_ROWS_CACHE, ensure_ascii=False, sort_keys=True
    ):
        return {
            "sheet": "supabase:inventory_purchase_orders" if _supabase_enabled_for("inventory_purchase_orders") else settings.google_sheets_inventory_purchase_orders_tab,
            "rows_saved": len(normalized_rows),
            "skipped": True,
        }
    if _supabase_enabled_for("inventory_purchase_orders"):
        result = supabase_store.replace_domain_rows("inventory_purchase_orders", normalized_rows)
        _INVENTORY_PURCHASE_ORDER_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _INVENTORY_PURCHASE_ORDER_ROWS_CACHE_TS = time.time()
        _save_inventory_purchase_order_disk_cache(normalized_rows)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_inventory_purchase_orders_sheet(service)
    values = [INVENTORY_PURCHASE_ORDER_HEADERS] + [
        [row.get(field, "") for field in INVENTORY_PURCHASE_ORDER_FIELDS]
        for row in normalized_rows
    ]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1:AA",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _INVENTORY_PURCHASE_ORDER_ROWS_CACHE = [dict(row) for row in normalized_rows]
    _INVENTORY_PURCHASE_ORDER_ROWS_CACHE_TS = time.time()
    _save_inventory_purchase_order_disk_cache(normalized_rows)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def save_working_order_rows(rows: list[dict]) -> dict:
    global _WORKING_ORDER_ROWS_CACHE, _WORKING_ORDER_ROWS_CACHE_TS
    normalized_rows = [_normalize_working_order_row(row) for row in (rows or [])]
    normalized_rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(
        _WORKING_ORDER_ROWS_CACHE, ensure_ascii=False, sort_keys=True
    ):
        return {"sheet": "supabase:working_orders" if _supabase_enabled_for("working_orders") else settings.google_sheets_working_orders_tab, "rows_saved": len(normalized_rows), "skipped": True}
    if _supabase_enabled_for("working_orders"):
        result = supabase_store.replace_domain_rows("working_orders", normalized_rows)
        _WORKING_ORDER_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _WORKING_ORDER_ROWS_CACHE_TS = time.time()
        _save_working_order_disk_cache(normalized_rows)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_working_orders_sheet(service)
    values = [WORKING_ORDER_HEADERS] + [
        [row.get(field, "") for field in WORKING_ORDER_FIELDS]
        for row in normalized_rows
    ]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1:AL",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _WORKING_ORDER_ROWS_CACHE = [dict(row) for row in normalized_rows]
    _WORKING_ORDER_ROWS_CACHE_TS = time.time()
    _save_working_order_disk_cache(normalized_rows)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def save_pricing_rows(kind: str, rows: list[dict]) -> dict:
    global _PRICING_ITEM_ROWS_CACHE, _PRICING_ITEM_ROWS_CACHE_TS, _PRICING_COMPONENT_ROWS_CACHE, _PRICING_COMPONENT_ROWS_CACHE_TS
    normalizer = _normalize_pricing_component_row if kind == "components" else _normalize_pricing_item_row
    fields = PRICING_COMPONENT_FIELDS if kind == "components" else PRICING_ITEM_FIELDS
    headers = PRICING_COMPONENT_HEADERS if kind == "components" else PRICING_ITEM_HEADERS
    normalized_rows = [normalizer(row) for row in (rows or [])]
    normalized_rows.sort(
        key=(
            (lambda row: (str(row.get("item_id") or ""), int(str(row.get("line_order") or "0") or 0), str(row.get("component_id") or "")))
            if kind == "components"
            else (lambda row: (str(row.get("kind") or ""), str(row.get("name") or "")))
        )
    )
    current_cache = _PRICING_COMPONENT_ROWS_CACHE if kind == "components" else _PRICING_ITEM_ROWS_CACHE
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(current_cache, ensure_ascii=False, sort_keys=True):
        return {
            "sheet": f"supabase:{_supabase_domain_for_pricing_kind(kind)}"
            if (_supabase_domain_for_pricing_kind(kind) and _supabase_enabled_for(_supabase_domain_for_pricing_kind(kind) or ""))
            else (settings.google_sheets_pricing_components_tab if kind == "components" else settings.google_sheets_pricing_items_tab),
            "rows_saved": len(normalized_rows),
            "skipped": True,
        }
    supabase_domain = _supabase_domain_for_pricing_kind(kind)
    if supabase_domain and _supabase_enabled_for(supabase_domain):
        result = supabase_store.replace_domain_rows(supabase_domain, normalized_rows)
        if kind == "components":
            _PRICING_COMPONENT_ROWS_CACHE = [dict(row) for row in normalized_rows]
            _PRICING_COMPONENT_ROWS_CACHE_TS = time.time()
            _save_pricing_components_disk_cache(normalized_rows)
        else:
            _PRICING_ITEM_ROWS_CACHE = [dict(row) for row in normalized_rows]
            _PRICING_ITEM_ROWS_CACHE_TS = time.time()
            _save_pricing_items_disk_cache(normalized_rows)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_pricing_sheet(service, kind)
    values = [headers] + [[row.get(field, "") for field in fields] for row in normalized_rows]
    end_column = "T" if kind == "components" else "O"
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1:{end_column}",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    if kind == "components":
        _PRICING_COMPONENT_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _PRICING_COMPONENT_ROWS_CACHE_TS = time.time()
        _save_pricing_components_disk_cache(normalized_rows)
    else:
        _PRICING_ITEM_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _PRICING_ITEM_ROWS_CACHE_TS = time.time()
        _save_pricing_items_disk_cache(normalized_rows)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def get_cached_order_history_rows() -> list[dict]:
    if _ORDER_HISTORY_ROWS_CACHE:
        return [dict(row) for row in _ORDER_HISTORY_ROWS_CACHE]
    return _load_order_history_disk_cache()


def get_cached_quote_history_rows() -> list[dict]:
    if _QUOTE_HISTORY_ROWS_CACHE:
        return [dict(row) for row in _QUOTE_HISTORY_ROWS_CACHE]
    return _load_quote_history_disk_cache()


def get_cached_installation_case_rows() -> list[dict]:
    if _INSTALLATION_CASE_ROWS_CACHE:
        return [dict(row) for row in _INSTALLATION_CASE_ROWS_CACHE]
    return _load_installation_cases_disk_cache()


def get_cached_installation_visit_rows() -> list[dict]:
    if _INSTALLATION_VISIT_ROWS_CACHE:
        return [dict(row) for row in _INSTALLATION_VISIT_ROWS_CACHE]
    return _load_installation_visits_disk_cache()


def get_cached_pazomat_rows() -> list[dict]:
    if _PAZOMAT_ROWS_CACHE:
        return [dict(row) for row in _PAZOMAT_ROWS_CACHE]
    return _load_pazomat_disk_cache()


def get_cached_sibus_rows() -> list[dict]:
    if _SIBUS_ROWS_CACHE:
        return [dict(row) for row in _SIBUS_ROWS_CACHE]
    return _load_sibus_disk_cache()


def get_cached_supplier_delivery_note_rows() -> list[dict]:
    if _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE:
        return [dict(row) for row in _SUPPLIER_DELIVERY_NOTE_ROWS_CACHE]
    return _load_supplier_delivery_note_disk_cache()


def get_cached_inventory_purchase_order_rows() -> list[dict]:
    if _INVENTORY_PURCHASE_ORDER_ROWS_CACHE:
        return [dict(row) for row in _INVENTORY_PURCHASE_ORDER_ROWS_CACHE]
    return _load_inventory_purchase_order_disk_cache()


def get_cached_pricing_rows(kind: str) -> list[dict]:
    if kind == "components":
        if _PRICING_COMPONENT_ROWS_CACHE:
            return [dict(row) for row in _PRICING_COMPONENT_ROWS_CACHE]
        return _load_pricing_components_disk_cache()
    if _PRICING_ITEM_ROWS_CACHE:
        return [dict(row) for row in _PRICING_ITEM_ROWS_CACHE]
    return _load_pricing_items_disk_cache()


def append_order_history_row(entry: dict) -> dict:
    rows = load_order_history_rows()
    normalized = _normalize_order_history_row(entry)
    if not normalized.get("history_id"):
        normalized["history_id"] = datetime.now().strftime("%Y%m%d%H%M%S%f")
    normalized["updated_at"] = datetime.now().isoformat(timespec="seconds")
    rows.insert(0, normalized)
    save_result = save_order_history_rows(rows)
    return {"status": "ok", "row": normalized, "save_result": save_result}


def upsert_order_history_row(entry: dict) -> dict:
    rows = load_order_history_rows()
    normalized = _normalize_order_history_row(entry)
    if not normalized.get("history_id"):
        normalized["history_id"] = datetime.now().strftime("%Y%m%d%H%M%S%f")
    normalized["updated_at"] = datetime.now().isoformat(timespec="seconds")
    updated = False
    for index, row in enumerate(rows):
        if str(row.get("history_id") or "").strip() != normalized["history_id"]:
            continue
        rows[index] = normalized
        updated = True
        break
    if not updated:
        rows.insert(0, normalized)
    save_result = save_order_history_rows(rows)
    return {"status": "ok", "row": normalized, "rows": rows, "updated": updated, "save_result": save_result}


def upsert_installation_case_row(entry: dict) -> dict:
    rows = load_installation_case_rows()
    normalized = _normalize_installation_case_row(entry)
    normalized["updated_at"] = datetime.now().isoformat(timespec="seconds")
    updated = False
    for index, row in enumerate(rows):
        if str(row.get("installation_id") or "").strip() != normalized["installation_id"]:
            continue
        rows[index] = normalized
        updated = True
        break
    if not updated:
        rows.insert(0, normalized)
    save_result = save_installation_case_rows(rows)
    return {"status": "ok", "row": normalized, "rows": rows, "updated": updated, "save_result": save_result}


def upsert_installation_visit_row(entry: dict) -> dict:
    rows = load_installation_visit_rows()
    normalized = _normalize_installation_visit_row(entry)
    normalized["updated_at"] = datetime.now().isoformat(timespec="seconds")
    updated = False
    for index, row in enumerate(rows):
        if str(row.get("visit_id") or "").strip() != normalized["visit_id"]:
            continue
        rows[index] = normalized
        updated = True
        break
    if not updated:
        rows.insert(0, normalized)
    save_result = save_installation_visit_rows(rows)
    return {"status": "ok", "row": normalized, "rows": rows, "updated": updated, "save_result": save_result}


def append_quote_history_row(entry: dict) -> dict:
    global _QUOTE_HISTORY_ROWS_CACHE, _QUOTE_HISTORY_ROWS_CACHE_TS
    try:
        rows = load_quote_history_rows()
    except Exception:
        rows = get_cached_quote_history_rows()
    normalized = _normalize_quote_history_row(entry)
    if not normalized.get("history_id"):
        normalized["history_id"] = datetime.now().strftime("%Y%m%d%H%M%S%f")
    normalized["updated_at"] = datetime.now().isoformat(timespec="seconds")
    rows = [
        row
        for row in rows
        if str(row.get("history_id") or "").strip() != str(normalized.get("history_id") or "").strip()
    ]
    rows.insert(0, normalized)
    try:
        save_result = save_quote_history_rows(rows)
        return {"status": "ok", "row": normalized, "save_result": save_result}
    except Exception as exc:
        fallback_rows = [_normalize_quote_history_row(row) for row in rows]
        fallback_rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
        _QUOTE_HISTORY_ROWS_CACHE = [dict(row) for row in fallback_rows]
        _QUOTE_HISTORY_ROWS_CACHE_TS = time.time()
        _save_quote_history_disk_cache(fallback_rows)
        return {
            "status": "stale",
            "row": normalized,
            "rows": fallback_rows,
            "warning": "ההצעה נשמרה זמנית בהיסטוריה המקומית, אבל הסנכרון המלא לגוגל שיטס לא הושלם כרגע.",
            "save_error": str(exc),
        }


def append_inventory_purchase_order_row(entry: dict) -> dict:
    rows = load_inventory_purchase_order_rows()
    normalized = _normalize_inventory_purchase_order_row(entry)
    if not normalized.get("history_id"):
        normalized["history_id"] = datetime.now().strftime("%Y%m%d%H%M%S%f")
    normalized["updated_at"] = datetime.now().isoformat(timespec="seconds")
    rows.insert(0, normalized)
    save_result = save_inventory_purchase_order_rows(rows)
    return {"status": "ok", "row": normalized, "save_result": save_result}


def delete_quote_history_row(history_id: str) -> dict:
    target_id = str(history_id or "").strip()
    if not target_id:
        raise ValueError("חסר מזהה היסטוריה למחיקה.")
    rows = load_quote_history_rows()
    remaining_rows = [row for row in rows if str(row.get("history_id") or "").strip() != target_id]
    deleted = len(rows) - len(remaining_rows)
    save_result = save_quote_history_rows(remaining_rows)
    return {"status": "ok", "deleted": deleted, "save_result": save_result, "rows": remaining_rows}


def delete_order_history_row(history_id: str) -> dict:
    target_id = str(history_id or "").strip()
    if not target_id:
        raise ValueError("חסר מזהה היסטוריה למחיקה.")
    rows = load_order_history_rows()
    remaining_rows = [row for row in rows if str(row.get("history_id") or "").strip() != target_id]
    deleted = len(rows) - len(remaining_rows)
    save_result = save_order_history_rows(remaining_rows)
    return {"status": "ok", "deleted": deleted, "save_result": save_result, "rows": remaining_rows}


def delete_delivery_confirmation_rows(
    *,
    history_id: str = "",
    fulfillment_id: str = "",
    po_number: str = "",
    source_mode: str = "",
    company: str = "",
    delivery_document_number: str = "",
    tax_invoice_number: str = "",
) -> dict:
    target_history_id = str(history_id or "").strip()
    target_fulfillment_id = str(fulfillment_id or "").strip()
    target_po_number = str(po_number or "").strip()
    target_source_mode = str(source_mode or "").strip().upper()
    target_company = _canonical_income_customer_name(company) or str(company or "").strip()
    target_delivery_document_number = str(delivery_document_number or "").strip()
    target_tax_invoice_number = str(tax_invoice_number or "").strip()
    if not any([target_history_id, target_fulfillment_id, target_po_number, target_delivery_document_number, target_tax_invoice_number]):
        raise ValueError("חסר מזהה למחיקת רשומת אישור מסירה.")

    rows = load_delivery_confirmation_rows()
    remaining_rows: list[dict] = []
    deleted_rows: list[dict] = []

    for row in rows:
        row_history_id = str(row.get("history_id") or "").strip()
        row_fulfillment_id = str(row.get("fulfillment_id") or "").strip()
        row_po_number = str(row.get("po_number") or "").strip()
        row_source_mode = str(row.get("source_mode") or "").strip().upper()
        row_company = _canonical_income_customer_name(row.get("company", "")) or str(row.get("company") or "").strip()
        row_delivery_document_number = str(row.get("delivery_document_number") or "").strip()
        row_tax_invoice_number = str(row.get("tax_invoice_number") or "").strip()

        matches = False
        if target_history_id and row_history_id == target_history_id:
            matches = True
        if target_fulfillment_id and row_fulfillment_id == target_fulfillment_id:
            matches = True
        if (
            not matches
            and target_delivery_document_number
            and row_delivery_document_number == target_delivery_document_number
            and (not target_source_mode or row_source_mode == target_source_mode)
            and (not target_po_number or row_po_number == target_po_number)
            and (not target_company or row_company == target_company)
        ):
            matches = True
        if (
            not matches
            and target_tax_invoice_number
            and row_tax_invoice_number == target_tax_invoice_number
            and (not target_source_mode or row_source_mode == target_source_mode)
            and (not target_po_number or row_po_number == target_po_number)
            and (not target_company or row_company == target_company)
        ):
            matches = True
        if (
            not matches
            and target_po_number
            and row_po_number == target_po_number
            and (not target_source_mode or row_source_mode == target_source_mode)
            and (not target_company or row_company == target_company)
            and (
                not target_delivery_document_number
                or row_delivery_document_number == target_delivery_document_number
            )
            and (
                not target_tax_invoice_number
                or row_tax_invoice_number == target_tax_invoice_number
            )
        ):
            matches = True

        if matches:
            deleted_rows.append(dict(row))
        else:
            remaining_rows.append(row)

    save_result = save_delivery_confirmation_rows(remaining_rows)
    return {
        "status": "ok",
        "deleted": len(deleted_rows),
        "deleted_rows": deleted_rows,
        "save_result": save_result,
        "rows": remaining_rows,
    }


def delete_inventory_purchase_order_row(history_id: str) -> dict:
    target_id = str(history_id or "").strip()
    if not target_id:
        raise ValueError("חסר מזהה היסטוריה למחיקה.")
    rows = load_inventory_purchase_order_rows()
    remaining_rows = [row for row in rows if str(row.get("history_id") or "").strip() != target_id]
    deleted = len(rows) - len(remaining_rows)
    save_result = save_inventory_purchase_order_rows(remaining_rows)
    return {"status": "ok", "deleted": deleted, "save_result": save_result, "rows": remaining_rows}


def update_inventory_purchase_order_send_status(history_id: str, send_status: str, sent_at: str = "") -> dict:
    target_id = str(history_id or "").strip()
    if not target_id:
        raise ValueError("חסר מזהה היסטוריה לעדכון סטטוס שליחה.")
    rows = load_inventory_purchase_order_rows()
    updated = None
    normalized_status = str(send_status or "").strip().lower()
    normalized_sent_at = str(sent_at or "").strip() or datetime.now().isoformat(timespec="seconds")
    for row in rows:
        if str(row.get("history_id") or "").strip() != target_id:
            continue
        row["send_status"] = normalized_status
        row["sent_at"] = normalized_sent_at
        row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        updated = _normalize_inventory_purchase_order_row(row)
        row.update(updated)
        break
    if not updated:
        raise ValueError("לא נמצאה הזמנת רכש לעדכון סטטוס שליחה.")
    save_result = save_inventory_purchase_order_rows(rows)
    return {"status": "ok", "row": updated, "rows": rows, "save_result": save_result}


def update_order_history_delivery_sent(
    po_number: str,
    tax_invoice_number: str = "",
    sent: bool = True,
    *,
    source_mode: str = "",
    customer_name: str = "",
    sent_label: str | None = None,
) -> dict:
    def _normalize_delivery_po_match_value(value: str) -> str:
        normalized_po_number = str(value or "").strip()
        if re.fullmatch(r"\d+", normalized_po_number):
            try:
                normalized_po_number = str(int(normalized_po_number))
            except Exception:
                normalized_po_number = normalized_po_number.lstrip("0") or "0"
        return normalized_po_number

    target_po = _normalize_delivery_po_match_value(po_number)
    target_invoice = str(tax_invoice_number or "").strip()
    target_mode = str(source_mode or "").strip().upper()
    target_customer = _canonical_income_customer_name(customer_name)
    if not target_po and not target_invoice:
        return {"status": "skipped", "reason": "missing_po_number_and_invoice"}
    rows = load_order_history_rows()
    updated = False
    normalized_sent = _normalize_order_history_sent(sent_label) if sent_label is not None else ("כן" if sent else "לא")
    for row in rows:
        row_po = _normalize_delivery_po_match_value(row.get("po_number") or "")
        row_invoice = str(row.get("tax_invoice_number") or "").strip()
        row_mode = str(row.get("mode") or row.get("source_mode") or "").strip().upper()
        row_customer = _canonical_income_customer_name(row.get("customer_name", ""))
        if target_po and row_po != target_po:
            continue
        if target_invoice and row_invoice and row_invoice != target_invoice:
            continue
        if target_mode and row_mode and row_mode != target_mode:
            continue
        if target_customer and row_customer and row_customer != target_customer:
            continue
        row["delivery_confirmation_sent"] = normalized_sent
        row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        updated = True
        break
    if not updated and target_invoice:
        for row in rows:
            row_invoice = str(row.get("tax_invoice_number") or "").strip()
            row_mode = str(row.get("mode") or row.get("source_mode") or "").strip().upper()
            row_customer = _canonical_income_customer_name(row.get("customer_name", ""))
            if row_invoice != target_invoice:
                continue
            if target_mode and row_mode and row_mode != target_mode:
                continue
            if target_customer and row_customer and row_customer != target_customer:
                continue
            row["delivery_confirmation_sent"] = normalized_sent
            row["updated_at"] = datetime.now().isoformat(timespec="seconds")
            updated = True
            break
    if not updated:
        return {"status": "skipped", "reason": "row_not_found"}
    save_result = save_order_history_rows(rows)
    return {"status": "ok", "save_result": save_result}


def _sort_marketing_rows(kind: str, rows: list[dict]) -> list[dict]:
    if kind == "history":
        rows.sort(key=lambda row: str(row.get("created_at") or ""), reverse=True)
    elif kind == "reminders":
        rows.sort(
            key=lambda row: (
                str(row.get("status") or ""),
                str(row.get("due_date") or ""),
                str(row.get("customer_name") or ""),
            )
        )
    elif kind == "work_managers":
        rows.sort(key=lambda row: (str(row.get("full_name") or ""), str(row.get("company_name") or "")))
    elif kind == "construction_companies":
        rows.sort(key=lambda row: (str(row.get("company_name") or ""), str(row.get("company_id") or "")))
    elif kind == "finance_invoices":
        rows.sort(
            key=lambda row: (
                str(row.get("invoice_date") or ""),
                str(row.get("supplier_name") or ""),
                str(row.get("service_or_product") or ""),
            ),
            reverse=True,
        )
    elif kind == "finance_settings":
        rows.sort(key=lambda row: str(row.get("setting_key") or ""))
    elif kind == "finance_customer_withholdings":
        rows.sort(
            key=lambda row: (
                str(row.get("receipt_date") or ""),
                str(row.get("customer_name") or ""),
                str(row.get("receipt_number") or ""),
            ),
            reverse=True,
        )
    elif kind == "finance_bank_movements":
        rows.sort(
            key=lambda row: (
                _payment_date_sort_key(str(row.get("transaction_date") or "")),
                _payment_date_sort_key(str(row.get("value_date") or "")),
                str(row.get("account_number") or ""),
                str(row.get("reference") or ""),
                str(row.get("description") or ""),
            ),
            reverse=True,
        )
    else:
        rows.sort(key=lambda row: (str(row.get("customer_name") or ""), str(row.get("customer_id") or "")))
    return rows


def load_marketing_rows(kind: str, force_refresh: bool = False) -> list[dict]:
    cache_rows, cache_ts = _get_marketing_cache(kind)
    if (
        not force_refresh
        and cache_rows
        and (time.time() - cache_ts) <= _GENERIC_SHEET_CACHE_TTL_SECONDS
    ):
        return [dict(row) for row in cache_rows]
    supabase_domain = _supabase_domain_for_marketing_kind(kind)
    if supabase_domain:
        try:
            rows = [_normalize_marketing_row(kind, row) for row in supabase_store.fetch_domain_rows(supabase_domain)]
            rows = _sort_marketing_rows(kind, rows)
            _set_marketing_cache(kind, rows)
            _save_marketing_disk_cache(kind, rows)
            return rows
        except Exception:
            if cache_rows:
                return [dict(row) for row in cache_rows]
            disk_rows = _load_marketing_disk_cache(kind)
            if disk_rows:
                return disk_rows
            raise
    service = _service()
    try:
        title, _ = _ensure_marketing_sheet(service, kind)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if cache_rows:
                return [dict(row) for row in cache_rows]
            disk_rows = _load_marketing_disk_cache(kind)
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:Z",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if cache_rows:
                return [dict(row) for row in cache_rows]
            disk_rows = _load_marketing_disk_cache(kind)
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    fields = _marketing_fields(kind)
    rows: list[dict] = []
    for raw in values:
        if kind == "construction_companies" and len(raw) == len(fields) - 1:
            raw = list(raw[:-1]) + ["", raw[-1]]
        padded = raw + [""] * max(0, len(fields) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(fields)}
        if any(str(value).strip() for value in row.values()):
            rows.append(_normalize_marketing_row(kind, row))
    rows = _sort_marketing_rows(kind, rows)
    _set_marketing_cache(kind, rows)
    _save_marketing_disk_cache(kind, rows)
    return rows


def save_marketing_rows(kind: str, rows: list[dict]) -> dict:
    normalized_rows = [_normalize_marketing_row(kind, row) for row in (rows or [])]
    normalized_rows = _sort_marketing_rows(kind, normalized_rows)
    cached_rows, _ = _get_marketing_cache(kind)
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(
        cached_rows, ensure_ascii=False, sort_keys=True
    ):
        return {
            "sheet": f"supabase:{kind}" if _supabase_domain_for_marketing_kind(kind) else kind,
            "rows_saved": len(normalized_rows),
            "skipped": True,
        }
    supabase_domain = _supabase_domain_for_marketing_kind(kind)
    if supabase_domain:
        result = supabase_store.replace_domain_rows(supabase_domain, normalized_rows)
        _set_marketing_cache(kind, normalized_rows)
        _save_marketing_disk_cache(kind, normalized_rows)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_marketing_sheet(service, kind)

    headers = _marketing_headers(kind)
    fields = _marketing_fields(kind)
    values = [headers] + [[row.get(field, "") for field in fields] for row in normalized_rows]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A2:Z",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _set_marketing_cache(kind, normalized_rows)
    _save_marketing_disk_cache(kind, normalized_rows)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def get_cached_marketing_rows(kind: str) -> list[dict]:
    cache_rows, _ = _get_marketing_cache(kind)
    if cache_rows:
        return [dict(row) for row in cache_rows]
    return _load_marketing_disk_cache(kind)


def upsert_marketing_note(row: dict) -> dict:
    normalized = _normalize_marketing_note_row(row)
    customer_key = str(normalized.get("customer_key") or "").strip()
    if not customer_key:
        raise ValueError("חסר מפתח לקוח לשמירת הערת שיווק.")
    rows = load_marketing_rows("notes")
    updated = False
    for index, existing in enumerate(rows):
        if str(existing.get("customer_key") or "").strip() == customer_key:
            rows[index] = normalized
            updated = True
            break
    if not updated:
        rows.append(normalized)
    save_result = save_marketing_rows("notes", rows)
    return {"status": "ok", "row": normalized, "save_result": save_result, "created": not updated}


def append_marketing_history_row(entry: dict) -> dict:
    rows = load_marketing_rows("history")
    normalized = _normalize_marketing_history_row(entry)
    if not normalized.get("history_id"):
        normalized["history_id"] = datetime.now().strftime("%Y%m%d%H%M%S%f")
    rows.insert(0, normalized)
    save_result = save_marketing_rows("history", rows)
    return {"status": "ok", "row": normalized, "save_result": save_result}


def upsert_marketing_reminder(row: dict) -> dict:
    normalized = _normalize_marketing_reminder_row(row)
    reminder_id = str(normalized.get("reminder_id") or "").strip()
    if not reminder_id:
        reminder_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
        normalized["reminder_id"] = reminder_id
    rows = load_marketing_rows("reminders")
    updated = False
    for index, existing in enumerate(rows):
        if str(existing.get("reminder_id") or "").strip() == reminder_id:
            rows[index] = normalized
            updated = True
            break
    if not updated:
        rows.append(normalized)
    save_result = save_marketing_rows("reminders", rows)
    return {"status": "ok", "row": normalized, "save_result": save_result, "created": not updated}


def _spreadsheet_metadata(service):
    global _SPREADSHEET_METADATA_CACHE, _SPREADSHEET_METADATA_CACHE_TS
    if (
        _SPREADSHEET_METADATA_CACHE is not None
        and (time.time() - _SPREADSHEET_METADATA_CACHE_TS) <= _SPREADSHEET_METADATA_CACHE_TTL_SECONDS
    ):
        return copy.deepcopy(_SPREADSHEET_METADATA_CACHE)
    metadata = service.spreadsheets().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        fields="sheets(properties(sheetId,title))",
    ).execute()
    _SPREADSHEET_METADATA_CACHE = copy.deepcopy(metadata)
    _SPREADSHEET_METADATA_CACHE_TS = time.time()
    return metadata


def _sheet_id_by_title(service, title: str):
    if title in _SHEET_ID_CACHE:
        return _SHEET_ID_CACHE[title]
    metadata = _spreadsheet_metadata(service)
    for sheet in metadata.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == title:
            sheet_id = props.get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id
            return sheet_id
    _SHEET_ID_CACHE[title] = None
    return None


def _is_rate_limit_error(exc: Exception) -> bool:
    return isinstance(exc, HttpError) and getattr(getattr(exc, "resp", None), "status", None) == 429


def _is_sheet_transient_error(exc: Exception) -> bool:
    if _is_rate_limit_error(exc):
        return True
    if isinstance(exc, TimeoutError):
        return True
    fragments: list[str] = []
    current: Exception | None = exc
    seen: set[int] = set()
    while current and id(current) not in seen:
        seen.add(id(current))
        fragments.append(f"{type(current).__name__}: {current}")
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    text = " | ".join(fragments).lower()
    return any(
        marker in text
        for marker in (
            "timed out",
            "timeout",
            "transporterror",
            "unable to find the server",
            "servernotfounderror",
            "connection reset",
            "connection aborted",
            "connection refused",
            "temporary failure",
            "temporarily unavailable",
        )
    )


def _load_project_managers_disk_cache() -> list[dict]:
    global _PROJECT_MANAGERS_ROWS_CACHE, _PROJECT_MANAGERS_ROWS_CACHE_TS
    try:
        if not _PROJECT_MANAGERS_CACHE_FILE.exists():
            return []
        payload = json.loads(_PROJECT_MANAGERS_CACHE_FILE.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else []
        normalized = _merge_project_manager_rows(rows)
        _PROJECT_MANAGERS_ROWS_CACHE = [dict(row) for row in normalized]
        _PROJECT_MANAGERS_ROWS_CACHE_TS = time.time()
        return [dict(row) for row in normalized]
    except Exception:
        return []


def _save_project_managers_disk_cache(rows: list[dict]) -> None:
    try:
        _PROJECT_MANAGERS_CACHE_FILE.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _load_delivery_disk_cache(kind: str) -> list[dict]:
    global _DELIVERY_CONFIRMATION_ROWS_CACHE, _DELIVERY_CONTACT_ROWS_CACHE, _DELIVERY_CONFIRMATION_ROWS_CACHE_TS, _DELIVERY_CONTACT_ROWS_CACHE_TS
    cache_file = _DELIVERY_CONFIRMATION_CACHE_FILE if kind == "confirmations" else _DELIVERY_CONTACTS_CACHE_FILE
    try:
        if not cache_file.exists():
            return []
        payload = json.loads(cache_file.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else []
        normalized = [_normalize_delivery_row(row, kind) for row in rows if isinstance(row, dict)]
        if kind == "confirmations":
            normalized.sort(
                key=lambda row: (
                    _project_manager_sort_ordinal(row.get("order_date", "")),
                    row.get("company", ""),
                    row.get("po_number", ""),
                ),
                reverse=True,
            )
            _DELIVERY_CONFIRMATION_ROWS_CACHE = [dict(row) for row in normalized]
            _DELIVERY_CONFIRMATION_ROWS_CACHE_TS = time.time()
        else:
            normalized.sort(key=lambda row: _canonicalize_project_manager_company(row.get("company", "")))
            _DELIVERY_CONTACT_ROWS_CACHE = [dict(row) for row in normalized]
            _DELIVERY_CONTACT_ROWS_CACHE_TS = time.time()
        return [dict(row) for row in normalized]
    except Exception:
        return []


def _save_delivery_disk_cache(kind: str, rows: list[dict]) -> None:
    cache_file = _DELIVERY_CONFIRMATION_CACHE_FILE if kind == "confirmations" else _DELIVERY_CONTACTS_CACHE_FILE
    try:
        cache_file.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def _ensure_inventory_sheet(service, kind: str):
    title = _inventory_tab_name(kind)
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    headers = _inventory_headers(kind)
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


def _normalize_inventory_row(row: dict, kind: str) -> dict:
    fields = _inventory_fields(kind)
    return {field: str((row or {}).get(field, "") or "") for field in fields}


def _ensure_delivery_sheet(service, kind: str):
    title = _delivery_tab_name(kind)
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    headers = _delivery_headers(kind)
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


def _normalize_delivery_row(row: dict, kind: str) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in _delivery_fields(kind)}
    if kind == "confirmations":
        def _looks_like_iso_datetime(value: str) -> bool:
            raw = str(value or "").strip()
            if not raw or "T" not in raw:
                return False
            try:
                datetime.fromisoformat(raw)
                return True
            except Exception:
                return False

        def _looks_like_human_date(value: str) -> bool:
            raw = str(value or "").strip()
            if not raw:
                return False
            for fmt in ("%d/%m/%Y", "%d/%m/%y", "%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S"):
                try:
                    datetime.strptime(raw, fmt)
                    return True
                except Exception:
                    continue
            return False

        def _looks_like_any_datetime(value: str) -> bool:
            raw = str(value or "").strip()
            if not raw:
                return False
            if _looks_like_iso_datetime(raw) or _looks_like_human_date(raw):
                return True
            return False

        legacy_source_mode = str(normalized.get("sent_at") or "").strip()
        if (
            not str(normalized.get("source_mode") or "").strip()
            and legacy_source_mode.upper() in {"SB", "PROD", "SANDBOX", "PRODUCTION"}
        ):
            legacy_order_drive_folder_id = str(normalized.get("coc_name") or "").strip()
            legacy_sent = str(normalized.get("coc_drive_file_id") or "").strip()
            legacy_sent_at = str(normalized.get("order_drive_folder_id") or "").strip()
            legacy_updated_at = str(normalized.get("sent") or "").strip()
            normalized["coc_name"] = ""
            normalized["coc_drive_file_id"] = ""
            normalized["order_drive_folder_id"] = legacy_order_drive_folder_id
            normalized["sent"] = legacy_sent
            normalized["sent_at"] = legacy_sent_at
            normalized["updated_at"] = legacy_updated_at or str(normalized.get("updated_at") or "")
            normalized["source_mode"] = legacy_source_mode
        raw_order_drive_folder_url = str(normalized.get("order_drive_folder_url") or "").strip()
        raw_fulfillment_id = str(normalized.get("fulfillment_id") or "").strip()
        raw_history_id = str(normalized.get("history_id") or "").strip()
        raw_document_mode = str(normalized.get("document_mode") or "").strip().lower()
        raw_sent = str(normalized.get("sent") or "").strip()
        raw_sent_at = str(normalized.get("sent_at") or "").strip()
        raw_updated_at = str(normalized.get("updated_at") or "").strip()
        raw_source_mode = str(normalized.get("source_mode") or "").strip()
        shifted_boolean_flag = raw_order_drive_folder_url.upper() in {"TRUE", "FALSE"}
        shifted_history_timestamp = _looks_like_iso_datetime(raw_history_id)
        shifted_sent_date = _looks_like_human_date(raw_fulfillment_id)
        if shifted_boolean_flag and (
            raw_sent.upper() in {"", "FALSE"}
            or (not raw_sent_at and shifted_sent_date)
            or shifted_history_timestamp
        ):
            normalized["sent"] = raw_order_drive_folder_url.upper()
            normalized["sent_at"] = raw_fulfillment_id if shifted_sent_date else raw_sent_at
            normalized["updated_at"] = raw_history_id if shifted_history_timestamp else (raw_updated_at or raw_history_id)
            normalized["order_drive_folder_url"] = (
                f"https://drive.google.com/drive/folders/{normalized.get('order_drive_folder_id', '').strip()}"
                if str(normalized.get("order_drive_folder_id") or "").strip()
                else ""
            )
            normalized["fulfillment_id"] = ""
            normalized["history_id"] = "" if shifted_history_timestamp else raw_history_id
            normalized["document_mode"] = raw_document_mode if raw_document_mode in {"full", "delivery_only", "invoice_only"} else "full"
            normalized["source_mode"] = raw_source_mode
        source_mode = str(normalized.get("source_mode") or "").strip().lower()
        normalized["source_mode"] = "SB" if source_mode in {"sb", "sandbox"} else "PROD" if source_mode in {"prod", "production"} else str(normalized.get("source_mode") or "").strip().upper()

        shifted_schema_detected = (
            str(normalized.get("updated_at") or "").strip().upper() in {"PROD", "SB", "SANDBOX", "PRODUCTION"}
            and _looks_like_iso_datetime(str(normalized.get("sent_at") or "").strip())
        )
        if shifted_schema_detected:
            current_signed_drive = str(normalized.get("signed_delivery_drive_file_id") or "").strip()
            current_invoice_drive = str(normalized.get("invoice_drive_file_id") or "").strip()
            current_coc_name = str(normalized.get("coc_name") or "").strip()
            current_coc_drive = str(normalized.get("coc_drive_file_id") or "").strip()
            current_folder_id = str(normalized.get("order_drive_folder_id") or "").strip()
            current_folder_url = str(normalized.get("order_drive_folder_url") or "").strip()
            current_fulfillment = str(normalized.get("fulfillment_id") or "").strip()
            current_history = str(normalized.get("history_id") or "").strip()
            current_document_mode = str(normalized.get("document_mode") or "").strip()
            current_delivery_number = str(normalized.get("delivery_document_number") or "").strip()
            current_delivery_id = str(normalized.get("delivery_document_id") or "").strip()
            current_sent = str(normalized.get("sent") or "").strip()
            current_sent_at = str(normalized.get("sent_at") or "").strip()
            current_updated_at = str(normalized.get("updated_at") or "").strip()
            current_source_mode = str(normalized.get("source_mode") or "").strip()

            normalized["signed_delivery_drive_file_id"] = ""
            normalized["invoice_drive_file_id"] = current_signed_drive
            normalized["coc_name"] = current_invoice_drive
            normalized["coc_drive_file_id"] = current_coc_name
            normalized["order_drive_folder_id"] = current_coc_drive
            normalized["order_drive_folder_url"] = current_folder_id
            normalized["fulfillment_id"] = current_folder_url
            normalized["history_id"] = current_fulfillment
            normalized["document_mode"] = current_history
            normalized["delivery_document_number"] = current_document_mode
            normalized["delivery_document_id"] = current_delivery_number
            normalized["sent"] = current_delivery_id
            normalized["sent_at"] = current_sent if _looks_like_any_datetime(current_sent) else ""
            normalized["updated_at"] = current_sent_at if _looks_like_any_datetime(current_sent_at) else ""
            normalized["source_mode"] = current_updated_at or current_source_mode
            normalized["_repair_delivery_confirmation_shifted_schema"] = "1"

        normalized["order_date"] = _format_date(normalized.get("order_date", ""))
        normalized["invoice_date"] = _format_date(normalized.get("invoice_date", ""))
        raw_order_total = str(normalized.get("order_total") or "").strip().replace(",", "")
        if raw_order_total:
            try:
                normalized["order_total"] = f"{float(raw_order_total):.2f}"
            except Exception:
                normalized["order_total"] = str(normalized.get("order_total") or "").strip()
        else:
            normalized["order_total"] = ""
        normalized["sent_at"] = _format_date(normalized.get("sent_at", "")) if "/" in str(normalized.get("sent_at", "")) else str(normalized.get("sent_at", "") or "")
        normalized["sent"] = "TRUE" if str(normalized.get("sent", "")).strip().lower() in {"1", "true", "yes", "on"} else "FALSE"
        normalized["order_drive_folder_url"] = str(normalized.get("order_drive_folder_url") or "").strip()
        normalized["fulfillment_id"] = str(normalized.get("fulfillment_id") or "").strip()
        normalized["history_id"] = str(normalized.get("history_id") or "").strip()
        raw_document_mode = str(normalized.get("document_mode") or "").strip().lower()
        normalized["document_mode"] = raw_document_mode if raw_document_mode in {"full", "delivery_only", "invoice_only"} else "full"
        normalized["delivery_document_number"] = str(normalized.get("delivery_document_number") or "").strip()
        normalized["delivery_document_id"] = str(normalized.get("delivery_document_id") or "").strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or datetime.now().isoformat(timespec="seconds"))
    return normalized


def _project_managers_tab_name() -> str:
    return settings.google_sheets_project_managers_tab


def _ensure_project_managers_sheet(service):
    title = _project_managers_tab_name()
    if title in _SHEET_ENSURED_CACHE:
        sheet_id = _SHEET_ID_CACHE.get(title)
        return title, sheet_id
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")
            _SHEET_ID_CACHE[title] = sheet_id

    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    if first_row != PROJECT_MANAGER_HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [PROJECT_MANAGER_HEADERS]},
        ).execute()
    _SHEET_ENSURED_CACHE.add(title)
    return title, sheet_id


def _normalize_project_manager_row(row: dict) -> dict:
    normalized = {field: str((row or {}).get(field, "") or "") for field in PROJECT_MANAGER_FIELDS}
    normalized["company"] = _canonicalize_project_manager_company(normalized.get("company", ""))
    normalized["tax_id"] = _canonicalize_project_manager_tax_id(normalized.get("tax_id", ""))
    normalized["contact_name"] = _canonicalize_project_manager_contact_name(normalized.get("contact_name", ""))
    normalized["contact_phone"] = _canonicalize_project_manager_phone(normalized.get("contact_phone", ""))
    return normalized


def _canonicalize_project_manager_company(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^\s*לכבוד\s*:\s*", "", text)
    text = re.sub(r"^\s*לקוח\s*:\s*", "", text)
    text = re.sub(r"^\s*לקו\s*ח\s*:\s*", "", text)
    text = (
        text.replace("״", '"')
        .replace("“", '"')
        .replace("”", '"')
        .replace("„", '"')
        .replace("׳", "'")
    )
    text = text.replace("פרוייקטים", "פרויקטים")
    text = text.replace("ייזום", "יזום")
    text = text.replace('"', "")
    text = re.sub(r"\bבעמ\b", 'בע"מ', text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    return text


def _canonicalize_project_manager_phone(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    digits = re.sub(r"\D+", "", raw)
    if len(digits) == 10 and digits.startswith("0"):
        return f"{digits[:3]}-{digits[3:]}"
    if len(digits) == 9 and digits.startswith("5"):
        return f"0{digits[:2]}-{digits[2:]}"
    return raw


def _canonicalize_project_manager_contact_name(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^\s*איש\s*קשר\s*[:.\-–—]*\s*", "", text)
    text = re.sub(r"\s+", " ", text).strip(" -.:,")
    return text


def _canonicalize_project_manager_tax_id(value: str) -> str:
    digits = re.sub(r"\D+", "", str(value or ""))
    return digits


def _project_manager_sort_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return __import__("datetime").datetime.strptime(value, fmt)
        except Exception:
            continue
    return None


def _project_manager_sort_ordinal(value: str) -> int:
    parsed = _project_manager_sort_date(value)
    return parsed.toordinal() if parsed else 0


def _project_manager_has_phone(row: dict) -> bool:
    digits = re.sub(r"\D+", "", str((row or {}).get("contact_phone", "") or ""))
    if len(digits) not in {9, 10}:
        return False
    if len(set(digits)) <= 2:
        return False
    if digits in FORBIDDEN_PROJECT_MANAGER_PHONES:
        return False
    if len(digits) == 9:
        return digits.startswith("5")
    return digits.startswith("0")


def _project_manager_has_core_fields(row: dict) -> bool:
    company = _canonicalize_project_manager_company((row or {}).get("company", ""))
    site_address = re.sub(r"\s+", " ", str((row or {}).get("site_address", "") or "").strip())
    return bool(company and site_address)


def _parse_history_dates(value: str) -> list[str]:
    raw_parts = re.split(r"[|,\n]+", value or "")
    values = []
    seen = set()
    for part in raw_parts:
        normalized = _format_date(part).strip()
        if normalized and normalized not in seen:
            values.append(normalized)
            seen.add(normalized)
    values.sort(key=lambda item: _project_manager_sort_date(item) or __import__("datetime").datetime.min, reverse=True)
    return values


def _serialize_history_dates(values: list[str]) -> str:
    seen = set()
    cleaned = []
    for value in values:
        normalized = _format_date(value).strip()
        if normalized and normalized not in seen:
            cleaned.append(normalized)
            seen.add(normalized)
    cleaned.sort(key=lambda item: _project_manager_sort_date(item) or __import__("datetime").datetime.min, reverse=True)
    return " | ".join(cleaned)


def _normalized_project_manager_key_parts(row: dict) -> tuple[str, str, str]:
    return (
        _canonicalize_project_manager_tax_id((row or {}).get("tax_id", "")) or re.sub(r"\s+", " ", str((row or {}).get("company", "") or "").strip().lower()),
        re.sub(r"\s+", " ", str((row or {}).get("site_address", "") or "").strip().lower()),
        re.sub(r"\D+", "", str((row or {}).get("contact_phone", "") or "")),
    )


def _project_manager_source_key(row: dict) -> str:
    return "|".join(_normalized_project_manager_key_parts(row))


def _project_manager_field_locked(row: dict, field_name: str) -> bool:
    value = str((row or {}).get(f"editable_{field_name}", "") or "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _merge_project_manager_rows(rows: list[dict]) -> list[dict]:
    merged_rows: list[dict] = []
    now_iso = __import__("datetime").datetime.now().isoformat(timespec="seconds")

    for row in rows or []:
        incoming = _normalize_project_manager_row(row)
        incoming["order_date"] = _format_date(incoming.get("order_date", ""))
        incoming["history_dates"] = _serialize_history_dates(_parse_history_dates(incoming.get("history_dates", "")))
        incoming["source_key"] = _project_manager_source_key(incoming)
        incoming["updated_at"] = incoming.get("updated_at") or now_iso
        if (
            not incoming["source_key"]
            or not _project_manager_has_phone(incoming)
            or not _project_manager_has_core_fields(incoming)
        ):
            continue

        match_index = next(
            (
                index
                for index, existing in enumerate(merged_rows)
                if (existing.get("source_key") or _project_manager_source_key(existing)) == incoming["source_key"]
            ),
            None,
        )

        if match_index is None:
            merged_rows.append(incoming)
            continue

        current = merged_rows[match_index]
        current_date = _project_manager_sort_date(current.get("order_date", ""))
        incoming_date = _project_manager_sort_date(incoming.get("order_date", ""))
        history_dates = _parse_history_dates(current.get("history_dates", ""))

        if incoming.get("order_date") and incoming.get("order_date") != current.get("order_date"):
            older_value = current.get("order_date", "")
            if current_date and incoming_date and incoming_date > current_date:
                if older_value:
                    history_dates.append(older_value)
            else:
                history_dates.append(incoming.get("order_date", ""))

        if not current_date or (incoming_date and incoming_date > current_date):
            for field_name in ("company", "tax_id", "site_address", "contact_name", "order_date", "item", "contact_phone"):
                if _project_manager_field_locked(current, field_name) and str(current.get(field_name, "") or "").strip():
                    continue
                incoming_value = str(incoming.get(field_name, "") or "").strip()
                if incoming_value:
                    current[field_name] = incoming_value
        else:
            for field_name in ("company", "tax_id", "site_address", "contact_name", "item", "contact_phone"):
                if str(current.get(field_name, "") or "").strip():
                    continue
                incoming_value = str(incoming.get(field_name, "") or "").strip()
                if incoming_value:
                    current[field_name] = incoming_value

        current_name = str(current.get("contact_name", "") or "").strip()
        incoming_name = str(incoming.get("contact_name", "") or "").strip()
        if incoming_name and not current_name:
            current["contact_name"] = incoming_name

        for editable_field in (
            "editable_company",
            "editable_tax_id",
            "editable_site_address",
            "editable_contact_name",
            "editable_order_date",
            "editable_item",
            "editable_contact_phone",
        ):
            if str(incoming.get(editable_field, "") or "").strip().lower() in {"1", "true", "yes", "on"}:
                current[editable_field] = "true"

        current["history_dates"] = _serialize_history_dates(history_dates)
        current["source_key"] = _project_manager_source_key(current)
        current["updated_at"] = incoming.get("updated_at") or now_iso

    return _dedupe_project_manager_rows_by_phone(merged_rows)


def _project_manager_row_score(row: dict) -> tuple:
    name = str((row or {}).get("contact_name", "") or "").strip()
    site_address = str((row or {}).get("site_address", "") or "").strip()
    company = str((row or {}).get("company", "") or "").strip()
    phone = str((row or {}).get("contact_phone", "") or "").strip()
    item = str((row or {}).get("item", "") or "").strip()
    order_ordinal = _project_manager_sort_ordinal(str((row or {}).get("order_date", "") or ""))
    return (
        1 if name else 0,
        len(name),
        1 if site_address else 0,
        len(site_address),
        order_ordinal,
        1 if company else 0,
        len(company),
        1 if item else 0,
        len(item),
        len(phone),
    )


def _dedupe_project_manager_rows_by_phone(rows: list[dict]) -> list[dict]:
    by_phone: dict[str, list[dict]] = {}
    passthrough: list[dict] = []

    for row in rows or []:
        phone = _canonicalize_project_manager_phone((row or {}).get("contact_phone", ""))
        if not phone:
            passthrough.append(row)
            continue
        by_phone.setdefault(phone, []).append(dict(row))

    deduped: list[dict] = []
    for phone, candidates in by_phone.items():
        best = max(candidates, key=_project_manager_row_score)
        history_dates = _parse_history_dates(best.get("history_dates", ""))

        for candidate in candidates:
            if candidate is best:
                continue
            for field_name in ("company", "tax_id", "site_address", "contact_name", "item", "contact_phone"):
                if str(best.get(field_name, "") or "").strip():
                    continue
                candidate_value = str(candidate.get(field_name, "") or "").strip()
                if candidate_value:
                    best[field_name] = candidate_value

            candidate_date = str(candidate.get("order_date", "") or "").strip()
            best_date = str(best.get("order_date", "") or "").strip()
            if candidate_date and candidate_date != best_date:
                history_dates.append(candidate_date)

            history_dates.extend(_parse_history_dates(candidate.get("history_dates", "")))

        best["history_dates"] = _serialize_history_dates(history_dates)
        best["source_key"] = _project_manager_source_key(best)
        deduped.append(best)

    combined = [*deduped, *passthrough]
    combined.sort(
        key=lambda row: (
            _canonicalize_project_manager_company(row.get("company", "")),
            _canonicalize_project_manager_phone(row.get("contact_phone", "")),
            -_project_manager_sort_ordinal(row.get("order_date", "")),
        )
    )
    return combined


def load_project_manager_rows() -> list[dict]:
    global _PROJECT_MANAGERS_ROWS_CACHE, _PROJECT_MANAGERS_ROWS_CACHE_TS
    if _PROJECT_MANAGERS_ROWS_CACHE and (time.time() - _PROJECT_MANAGERS_ROWS_CACHE_TS) <= _GENERIC_SHEET_CACHE_TTL_SECONDS:
        return [dict(row) for row in _PROJECT_MANAGERS_ROWS_CACHE]
    if _supabase_enabled_for("project_managers"):
        try:
            rows = _merge_project_manager_rows(supabase_store.fetch_domain_rows("project_managers"))
            rows.sort(
                key=lambda row: (
                    str(row.get("company", "") or ""),
                    str(row.get("site_address", "") or ""),
                    str(row.get("contact_name", "") or ""),
                    -_project_manager_sort_ordinal(row.get("order_date", "")),
                ),
            )
            _PROJECT_MANAGERS_ROWS_CACHE = [dict(row) for row in rows]
            _PROJECT_MANAGERS_ROWS_CACHE_TS = time.time()
            _save_project_managers_disk_cache(_PROJECT_MANAGERS_ROWS_CACHE)
            return rows
        except Exception:
            if _PROJECT_MANAGERS_ROWS_CACHE:
                return [dict(row) for row in _PROJECT_MANAGERS_ROWS_CACHE]
            disk_rows = _load_project_managers_disk_cache()
            if disk_rows:
                return disk_rows
            raise
    service = _service()
    try:
        title, _ = _ensure_project_managers_sheet(service)
    except Exception as exc:
        if _is_rate_limit_error(exc):
            if _PROJECT_MANAGERS_ROWS_CACHE:
                return [dict(row) for row in _PROJECT_MANAGERS_ROWS_CACHE]
            disk_rows = _load_project_managers_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1:Z",
        ).execute()
    except HttpError as exc:
        if _is_rate_limit_error(exc):
            if _PROJECT_MANAGERS_ROWS_CACHE:
                return [dict(row) for row in _PROJECT_MANAGERS_ROWS_CACHE]
            disk_rows = _load_project_managers_disk_cache()
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    if not values:
        return []
    raw_headers = values[0]
    data_rows = values[1:]
    raw_rows = []
    for raw in data_rows:
        row = {field: "" for field in PROJECT_MANAGER_FIELDS}
        for index, header in enumerate(raw_headers):
            field_name = PROJECT_MANAGER_HEADER_TO_FIELD.get(str(header or "").strip())
            if not field_name:
                continue
            if index < len(raw):
                row[field_name] = str(raw[index] or "")
        if not any(str(value).strip() for value in row.values()):
            continue
        row["source_key"] = _project_manager_source_key(row)
        raw_rows.append(row)
    rows = _merge_project_manager_rows(raw_rows)
    rows.sort(
        key=lambda row: (
            str(row.get("company", "") or ""),
            str(row.get("site_address", "") or ""),
            str(row.get("contact_name", "") or ""),
            -_project_manager_sort_ordinal(row.get("order_date", "")),
        ),
    )
    _PROJECT_MANAGERS_ROWS_CACHE = [dict(row) for row in rows]
    _PROJECT_MANAGERS_ROWS_CACHE_TS = time.time()
    _save_project_managers_disk_cache(_PROJECT_MANAGERS_ROWS_CACHE)
    return rows


def get_cached_project_manager_rows() -> list[dict]:
    if _PROJECT_MANAGERS_ROWS_CACHE:
        return [dict(row) for row in _PROJECT_MANAGERS_ROWS_CACHE]
    return _load_project_managers_disk_cache()


def save_project_manager_rows(rows: list[dict]) -> dict:
    global _PROJECT_MANAGERS_ROWS_CACHE, _PROJECT_MANAGERS_ROWS_CACHE_TS
    normalized_rows = _merge_project_manager_rows(rows)
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(_PROJECT_MANAGERS_ROWS_CACHE, ensure_ascii=False, sort_keys=True):
        return {
            "sheet": "supabase:project_managers" if _supabase_enabled_for("project_managers") else settings.google_sheets_project_managers_tab,
            "rows_saved": len(normalized_rows),
            "skipped": True,
        }
    if _supabase_enabled_for("project_managers"):
        result = supabase_store.replace_domain_rows("project_managers", normalized_rows)
        _PROJECT_MANAGERS_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _PROJECT_MANAGERS_ROWS_CACHE_TS = time.time()
        _save_project_managers_disk_cache(_PROJECT_MANAGERS_ROWS_CACHE)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_project_managers_sheet(service)

    values = [PROJECT_MANAGER_HEADERS] + [
        [row.get(field, "") for field in PROJECT_MANAGER_FIELDS]
        for row in normalized_rows
    ]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A2:Z",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _PROJECT_MANAGERS_ROWS_CACHE = [dict(row) for row in normalized_rows]
    _PROJECT_MANAGERS_ROWS_CACHE_TS = time.time()
    _save_project_managers_disk_cache(_PROJECT_MANAGERS_ROWS_CACHE)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def upsert_project_manager_rows(entries: list[dict]) -> dict:
    before_rows = load_project_manager_rows()
    after_rows = _merge_project_manager_rows([*before_rows, *(entries or [])])
    before_keys = {row.get("source_key", "") for row in before_rows}
    after_keys = {row.get("source_key", "") for row in after_rows}
    added = len(after_keys - before_keys)
    updated = max(0, len(after_rows) - added)
    save_result = save_project_manager_rows(after_rows)
    return {"status": "ok", "added": added, "updated": updated, "save_result": save_result}


def load_delivery_confirmation_rows() -> list[dict]:
    global _DELIVERY_CONFIRMATION_ROWS_CACHE, _DELIVERY_CONFIRMATION_ROWS_CACHE_TS
    if _DELIVERY_CONFIRMATION_ROWS_CACHE and (time.time() - _DELIVERY_CONFIRMATION_ROWS_CACHE_TS) <= _GENERIC_SHEET_CACHE_TTL_SECONDS:
        return [dict(row) for row in _DELIVERY_CONFIRMATION_ROWS_CACHE]
    if _supabase_enabled_for("delivery_confirmations"):
        try:
            rows = [_normalize_delivery_row(row, "confirmations") for row in supabase_store.fetch_domain_rows("delivery_confirmations")]
            rows.sort(
                key=lambda row: (
                    _project_manager_sort_ordinal(row.get("order_date", "")),
                    row.get("company", ""),
                    row.get("po_number", ""),
                ),
                reverse=True,
            )
            _DELIVERY_CONFIRMATION_ROWS_CACHE = [dict(row) for row in rows]
            _DELIVERY_CONFIRMATION_ROWS_CACHE_TS = time.time()
            _save_delivery_disk_cache("confirmations", _DELIVERY_CONFIRMATION_ROWS_CACHE)
            return rows
        except Exception:
            if _DELIVERY_CONFIRMATION_ROWS_CACHE:
                return [dict(row) for row in _DELIVERY_CONFIRMATION_ROWS_CACHE]
            disk_rows = _load_delivery_disk_cache("confirmations")
            if disk_rows:
                return disk_rows
            raise
    service = _service()
    try:
        title, _ = _ensure_delivery_sheet(service, "confirmations")
    except Exception as exc:
        if _is_sheet_transient_error(exc):
            if _DELIVERY_CONFIRMATION_ROWS_CACHE:
                return [dict(row) for row in _DELIVERY_CONFIRMATION_ROWS_CACHE]
            disk_rows = _load_delivery_disk_cache("confirmations")
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:Z",
        ).execute()
    except Exception as exc:
        if _is_sheet_transient_error(exc):
            if _DELIVERY_CONFIRMATION_ROWS_CACHE:
                return [dict(row) for row in _DELIVERY_CONFIRMATION_ROWS_CACHE]
            disk_rows = _load_delivery_disk_cache("confirmations")
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    fields = _delivery_fields("confirmations")
    rows: list[dict] = []
    needs_resave = False
    for raw in values:
        padded = raw + [""] * max(0, len(fields) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(fields)}
        if any(str(value).strip() for value in row.values()):
            if len(raw) > 13 and str(raw[13] or "").strip().upper() in {"TRUE", "FALSE"}:
                needs_resave = True
            normalized_row = _normalize_delivery_row(row, "confirmations")
            if str(normalized_row.pop("_repair_delivery_confirmation_shifted_schema", "")).strip():
                needs_resave = True
            rows.append(normalized_row)
    rows.sort(
        key=lambda row: (
            _project_manager_sort_ordinal(row.get("order_date", "")),
            row.get("company", ""),
            row.get("po_number", ""),
        ),
        reverse=True,
    )
    if needs_resave:
        try:
            current_cache = _DELIVERY_CONFIRMATION_ROWS_CACHE
            current_cache_ts = _DELIVERY_CONFIRMATION_ROWS_CACHE_TS
            _DELIVERY_CONFIRMATION_ROWS_CACHE = []
            _DELIVERY_CONFIRMATION_ROWS_CACHE_TS = 0
            save_delivery_confirmation_rows(rows)
            _DELIVERY_CONFIRMATION_ROWS_CACHE = [dict(row) for row in rows]
            _DELIVERY_CONFIRMATION_ROWS_CACHE_TS = time.time()
        except Exception:
            _DELIVERY_CONFIRMATION_ROWS_CACHE = current_cache
            _DELIVERY_CONFIRMATION_ROWS_CACHE_TS = current_cache_ts
    _DELIVERY_CONFIRMATION_ROWS_CACHE = [dict(row) for row in rows]
    _DELIVERY_CONFIRMATION_ROWS_CACHE_TS = time.time()
    _save_delivery_disk_cache("confirmations", _DELIVERY_CONFIRMATION_ROWS_CACHE)
    return rows


def save_delivery_confirmation_rows(rows: list[dict]) -> dict:
    global _DELIVERY_CONFIRMATION_ROWS_CACHE, _DELIVERY_CONFIRMATION_ROWS_CACHE_TS
    normalized_rows = [_normalize_delivery_row(row, "confirmations") for row in rows]
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(_DELIVERY_CONFIRMATION_ROWS_CACHE, ensure_ascii=False, sort_keys=True):
        return {
            "sheet": "supabase:delivery_confirmations" if _supabase_enabled_for("delivery_confirmations") else settings.google_sheets_delivery_confirmations_tab,
            "rows_saved": len(normalized_rows),
            "skipped": True,
        }
    if _supabase_enabled_for("delivery_confirmations"):
        result = supabase_store.replace_domain_rows("delivery_confirmations", normalized_rows)
        _DELIVERY_CONFIRMATION_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _DELIVERY_CONFIRMATION_ROWS_CACHE_TS = time.time()
        _save_delivery_disk_cache("confirmations", _DELIVERY_CONFIRMATION_ROWS_CACHE)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_delivery_sheet(service, "confirmations")
    values = [DELIVERY_CONFIRMATION_HEADERS] + [
        [row.get(field, "") for field in DELIVERY_CONFIRMATION_FIELDS]
        for row in normalized_rows
    ]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A2:Z",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _DELIVERY_CONFIRMATION_ROWS_CACHE = [dict(row) for row in normalized_rows]
    _DELIVERY_CONFIRMATION_ROWS_CACHE_TS = time.time()
    _save_delivery_disk_cache("confirmations", _DELIVERY_CONFIRMATION_ROWS_CACHE)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def upsert_delivery_confirmation_row(entry: dict) -> dict:
    rows = load_delivery_confirmation_rows()
    normalized = _normalize_delivery_row(entry, "confirmations")
    remove_delivery_confirmation_suppression(
        company=normalized.get("company", ""),
        po_number=normalized.get("po_number", ""),
        source_mode=normalized.get("source_mode", ""),
        tax_invoice_number=normalized.get("tax_invoice_number", ""),
        delivery_document_number=normalized.get("delivery_document_number", ""),
    )
    fulfillment_id = str(normalized.get("fulfillment_id", "") or "").strip()
    history_id = str(normalized.get("history_id", "") or "").strip()
    key = (
        _canonicalize_project_manager_company(normalized.get("company", "")),
        str(normalized.get("po_number", "") or "").strip(),
        str(normalized.get("tax_invoice_number", "") or "").strip(),
    )
    fallback_key = (
        _canonicalize_project_manager_company(normalized.get("company", "")),
        str(normalized.get("po_number", "") or "").strip(),
        str(normalized.get("source_mode", "") or "").strip().upper(),
    )
    normalized_invoice_number = str(normalized.get("tax_invoice_number", "") or "").strip()
    updated = False
    for row in rows:
        row_invoice_number = str(row.get("tax_invoice_number", "") or "").strip()
        if (
            fulfillment_id
            and str(row.get("fulfillment_id", "") or "").strip() == fulfillment_id
            and (
                not normalized_invoice_number
                or not row_invoice_number
                or row_invoice_number == normalized_invoice_number
            )
        ):
            for field in DELIVERY_CONFIRMATION_FIELDS:
                incoming_value = str(normalized.get(field, "") or "").strip()
                if incoming_value:
                    if (
                        field == "sent"
                        and str(row.get("sent", "")).strip().upper() == "TRUE"
                        and incoming_value.upper() == "FALSE"
                    ):
                        continue
                    row[field] = incoming_value
            row["updated_at"] = datetime.now().isoformat(timespec="seconds")
            updated = True
            break
        if history_id and str(row.get("history_id", "") or "").strip() == history_id and not str(row.get("fulfillment_id", "") or "").strip():
            for field in DELIVERY_CONFIRMATION_FIELDS:
                incoming_value = str(normalized.get(field, "") or "").strip()
                if incoming_value:
                    if (
                        field == "sent"
                        and str(row.get("sent", "")).strip().upper() == "TRUE"
                        and incoming_value.upper() == "FALSE"
                    ):
                        continue
                    row[field] = incoming_value
            row["updated_at"] = datetime.now().isoformat(timespec="seconds")
            updated = True
            break
        row_key = (
            _canonicalize_project_manager_company(row.get("company", "")),
            str(row.get("po_number", "") or "").strip(),
            str(row.get("tax_invoice_number", "") or "").strip(),
        )
        row_fallback_key = (
            _canonicalize_project_manager_company(row.get("company", "")),
            str(row.get("po_number", "") or "").strip(),
            str(row.get("source_mode", "") or "").strip().upper(),
        )
        if row_key != key and row_fallback_key != fallback_key:
            continue
        for field in DELIVERY_CONFIRMATION_FIELDS:
            incoming_value = str(normalized.get(field, "") or "").strip()
            if incoming_value:
                if (
                    field == "sent"
                    and str(row.get("sent", "")).strip().upper() == "TRUE"
                    and incoming_value.upper() == "FALSE"
                ):
                    continue
                row[field] = incoming_value
        row["updated_at"] = datetime.now().isoformat(timespec="seconds")
        updated = True
        break
    if not updated:
        normalized["updated_at"] = datetime.now().isoformat(timespec="seconds")
        rows.append(normalized)
    save_result = save_delivery_confirmation_rows(rows)
    return {"status": "ok", "updated": updated, "save_result": save_result}


def load_delivery_contact_rows() -> list[dict]:
    global _DELIVERY_CONTACT_ROWS_CACHE, _DELIVERY_CONTACT_ROWS_CACHE_TS
    if _DELIVERY_CONTACT_ROWS_CACHE and (time.time() - _DELIVERY_CONTACT_ROWS_CACHE_TS) <= _GENERIC_SHEET_CACHE_TTL_SECONDS:
        return [dict(row) for row in _DELIVERY_CONTACT_ROWS_CACHE]
    if _supabase_enabled_for("delivery_contacts"):
        try:
            rows = [_normalize_delivery_row(row, "contacts") for row in supabase_store.fetch_domain_rows("delivery_contacts")]
            rows.sort(key=lambda row: _canonicalize_project_manager_company(row.get("company", "")))
            _DELIVERY_CONTACT_ROWS_CACHE = [dict(row) for row in rows]
            _DELIVERY_CONTACT_ROWS_CACHE_TS = time.time()
            _save_delivery_disk_cache("contacts", _DELIVERY_CONTACT_ROWS_CACHE)
            return rows
        except Exception:
            if _DELIVERY_CONTACT_ROWS_CACHE:
                return [dict(row) for row in _DELIVERY_CONTACT_ROWS_CACHE]
            disk_rows = _load_delivery_disk_cache("contacts")
            if disk_rows:
                return disk_rows
            raise
    service = _service()
    try:
        title, _ = _ensure_delivery_sheet(service, "contacts")
    except Exception as exc:
        if _is_sheet_transient_error(exc):
            if _DELIVERY_CONTACT_ROWS_CACHE:
                return [dict(row) for row in _DELIVERY_CONTACT_ROWS_CACHE]
            disk_rows = _load_delivery_disk_cache("contacts")
            if disk_rows:
                return disk_rows
        raise
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A2:Z",
        ).execute()
    except Exception as exc:
        if _is_sheet_transient_error(exc):
            if _DELIVERY_CONTACT_ROWS_CACHE:
                return [dict(row) for row in _DELIVERY_CONTACT_ROWS_CACHE]
            disk_rows = _load_delivery_disk_cache("contacts")
            if disk_rows:
                return disk_rows
        raise
    values = result.get("values", [])
    fields = _delivery_fields("contacts")
    rows: list[dict] = []
    for raw in values:
        padded = raw + [""] * max(0, len(fields) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(fields)}
        if any(str(value).strip() for value in row.values()):
            rows.append(_normalize_delivery_row(row, "contacts"))
    rows.sort(key=lambda row: _canonicalize_project_manager_company(row.get("company", "")))
    _DELIVERY_CONTACT_ROWS_CACHE = [dict(row) for row in rows]
    _DELIVERY_CONTACT_ROWS_CACHE_TS = time.time()
    _save_delivery_disk_cache("contacts", _DELIVERY_CONTACT_ROWS_CACHE)
    return rows


def save_delivery_contact_rows(rows: list[dict]) -> dict:
    global _DELIVERY_CONTACT_ROWS_CACHE, _DELIVERY_CONTACT_ROWS_CACHE_TS
    normalized_rows = [_normalize_delivery_row(row, "contacts") for row in rows]
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(_DELIVERY_CONTACT_ROWS_CACHE, ensure_ascii=False, sort_keys=True):
        return {
            "sheet": "supabase:delivery_contacts" if _supabase_enabled_for("delivery_contacts") else settings.google_sheets_delivery_contacts_tab,
            "rows_saved": len(normalized_rows),
            "skipped": True,
        }
    if _supabase_enabled_for("delivery_contacts"):
        result = supabase_store.replace_domain_rows("delivery_contacts", normalized_rows)
        _DELIVERY_CONTACT_ROWS_CACHE = [dict(row) for row in normalized_rows]
        _DELIVERY_CONTACT_ROWS_CACHE_TS = time.time()
        _save_delivery_disk_cache("contacts", _DELIVERY_CONTACT_ROWS_CACHE)
        return {"sheet": f"supabase:{result['table']}", "rows_saved": len(normalized_rows), "deleted": result.get("deleted", 0)}

    service = _service()
    title, _ = _ensure_delivery_sheet(service, "contacts")
    values = [DELIVERY_CONTACT_HEADERS] + [
        [row.get(field, "") for field in DELIVERY_CONTACT_FIELDS]
        for row in normalized_rows
    ]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A2:Z",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _DELIVERY_CONTACT_ROWS_CACHE = [dict(row) for row in normalized_rows]
    _DELIVERY_CONTACT_ROWS_CACHE_TS = time.time()
    _save_delivery_disk_cache("contacts", _DELIVERY_CONTACT_ROWS_CACHE)
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def get_cached_delivery_confirmation_rows() -> list[dict]:
    if _DELIVERY_CONFIRMATION_ROWS_CACHE:
        return [dict(row) for row in _DELIVERY_CONFIRMATION_ROWS_CACHE]
    return _load_delivery_disk_cache("confirmations")


def get_cached_delivery_contact_rows() -> list[dict]:
    if _DELIVERY_CONTACT_ROWS_CACHE:
        return [dict(row) for row in _DELIVERY_CONTACT_ROWS_CACHE]
    return _load_delivery_disk_cache("contacts")


def build_delivery_contact_rows_for_active_orders(confirmations: list[dict], existing_rows: list[dict] | None = None) -> list[dict]:
    existing_rows = existing_rows or load_delivery_contact_rows()
    by_company: dict[str, dict] = {}
    for row in existing_rows:
        key = _canonicalize_project_manager_company(row.get("company", ""))
        if key:
            by_company[key] = _normalize_delivery_row(row, "contacts")

    def _split_delivery_emails(value: str) -> list[str]:
        parts = re.split(r"[\n,;]+", str(value or ""))
        return [part.strip() for part in parts if part and part.strip()]

    normalized_email_overrides = {
        _canonicalize_project_manager_company(company): str(email or "").strip()
        for company, email in DELIVERY_CONTACT_EMAIL_OVERRIDES_BY_COMPANY.items()
        if _canonicalize_project_manager_company(company) and str(email or "").strip()
    }

    def _confirmation_score(row: dict) -> tuple[int, int, str]:
        emails = _split_delivery_emails(row.get("target_email", ""))
        return (
            len(emails),
            len(str(row.get("target_email", "") or "").strip()),
            str(row.get("updated_at", "") or "").strip(),
        )

    best_confirmation_by_company: dict[str, dict] = {}
    for row in confirmations:
        key = _canonicalize_project_manager_company(row.get("company", ""))
        if not key:
            continue
        current_best = best_confirmation_by_company.get(key)
        if current_best is None or _confirmation_score(row) > _confirmation_score(current_best):
            best_confirmation_by_company[key] = dict(row)

    active_companies = set()
    for row in confirmations:
        company = _canonicalize_project_manager_company(row.get("company", ""))
        if not company:
            continue
        if "sent" in row:
            if str(row.get("sent", "")).strip().upper() == "TRUE":
                continue
        active_companies.add(company)
    active_companies = {company for company in active_companies if company}

    rows: list[dict] = []
    for company in sorted(active_companies):
        existing = dict(by_company.get(company) or {})
        fallback = dict(best_confirmation_by_company.get(company) or {})
        display_company = (
            str(existing.get("company", "") or "").strip()
            or str(fallback.get("company", "") or "").strip()
            or company
        )
        existing_email = str(existing.get("email", "") or "").strip()
        fallback_email = str(fallback.get("target_email", "") or "").strip()
        override_email = normalized_email_overrides.get(company, "")
        rows.append(
            _normalize_delivery_row(
                {
                    "company": display_company,
                    "accounting_contact_name": existing.get("accounting_contact_name", ""),
                    "phone": existing.get("phone", ""),
                    "mobile": existing.get("mobile", ""),
                    "email": override_email or existing_email or fallback_email,
                    "updated_at": existing.get("updated_at", ""),
                },
                "contacts",
            )
        )
    return rows


def _sandbox_deduction_tab_name() -> str:
    return "מלאי - הפחתות סנדבוקס"


def _ensure_sandbox_deduction_sheet(service):
    title = _sandbox_deduction_tab_name()
    sheet_id = _sheet_id_by_title(service, title)
    if sheet_id is None:
        body = {"requests": [{"addSheet": {"properties": {"title": title}}}]}
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            body=body,
        ).execute()
        replies = response.get("replies", [])
        if replies:
            sheet_id = replies[0].get("addSheet", {}).get("properties", {}).get("sheetId")

    current = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!1:1",
    ).execute().get("values", [])
    first_row = current[0] if current else []
    if first_row != SANDBOX_DEDUCTION_HEADERS:
        service.spreadsheets().values().update(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=f"{title}!A1",
            valueInputOption="RAW",
            body={"values": [SANDBOX_DEDUCTION_HEADERS]},
        ).execute()
    return title, sheet_id


def _load_sandbox_deduction_rows() -> list[dict]:
    service = _service()
    title, _ = _ensure_sandbox_deduction_sheet(service)
    result = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A2:AZ",
    ).execute()
    values = result.get("values", [])
    rows = []
    for raw in values:
        padded = raw + [""] * max(0, len(SANDBOX_DEDUCTION_FIELDS) - len(raw))
        row = {
            field: str(padded[index] or "")
            for index, field in enumerate(SANDBOX_DEDUCTION_FIELDS)
        }
        if any(str(value).strip() for value in row.values()):
            rows.append(row)
    return rows


def _save_sandbox_deduction_rows(rows: list[dict]) -> dict:
    service = _service()
    title, _ = _ensure_sandbox_deduction_sheet(service)
    normalized_rows = [
        {field: str((row or {}).get(field, "") or "") for field in SANDBOX_DEDUCTION_FIELDS}
        for row in rows
    ]
    values = [SANDBOX_DEDUCTION_HEADERS] + [
        [row.get(field, "") for field in SANDBOX_DEDUCTION_FIELDS]
        for row in normalized_rows
    ]
    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A2:AZ",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    return {"sheet": title, "rows_saved": len(normalized_rows)}


def load_inventory_rows(kind: str) -> list[dict]:
    cached_rows = _INVENTORY_ROWS_CACHE.get(kind) or []
    cached_ts = _INVENTORY_ROWS_CACHE_TS.get(kind, 0.0)
    if cached_rows and (time.time() - cached_ts) <= _GENERIC_SHEET_CACHE_TTL_SECONDS:
        return [dict(row) for row in cached_rows]
    supabase_domain = _supabase_domain_for_inventory_kind(kind)
    if supabase_domain and _supabase_enabled_for(supabase_domain):
        try:
            rows = [_normalize_inventory_row(row, kind) for row in supabase_store.fetch_domain_rows(supabase_domain)]
            _INVENTORY_ROWS_CACHE[kind] = [dict(row) for row in rows]
            _INVENTORY_ROWS_CACHE_TS[kind] = time.time()
            return rows
        except Exception:
            if cached_rows:
                return [dict(row) for row in cached_rows]
            raise
    service = _service()
    title, _ = _ensure_inventory_sheet(service, kind)
    fields = _inventory_fields(kind)
    result = service.spreadsheets().values().get(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A2:Z",
    ).execute()
    values = result.get("values", [])
    rows = []
    for raw in values:
        padded = raw + [""] * max(0, len(fields) - len(raw))
        row = {field: str(padded[index] or "") for index, field in enumerate(fields)}
        if any(str(value).strip() for value in row.values()):
            rows.append(row)
    _INVENTORY_ROWS_CACHE[kind] = [dict(row) for row in rows]
    _INVENTORY_ROWS_CACHE_TS[kind] = time.time()
    return rows


def save_inventory_rows(kind: str, rows: list[dict]) -> dict:
    normalized_rows = [_normalize_inventory_row(row, kind) for row in rows]
    if json.dumps(normalized_rows, ensure_ascii=False, sort_keys=True) == json.dumps(_INVENTORY_ROWS_CACHE.get(kind) or [], ensure_ascii=False, sort_keys=True):
        supabase_domain = _supabase_domain_for_inventory_kind(kind)
        return {
            "sheet": f"supabase:{supabase_domain}"
            if (supabase_domain and _supabase_enabled_for(supabase_domain))
            else _inventory_tab_name(kind),
            "rows_saved": len(normalized_rows),
            "skipped": True,
        }
    supabase_domain = _supabase_domain_for_inventory_kind(kind)
    if supabase_domain and _supabase_enabled_for(supabase_domain):
        result = supabase_store.replace_domain_rows(supabase_domain, normalized_rows)
        _INVENTORY_ROWS_CACHE[kind] = [dict(row) for row in normalized_rows]
        _INVENTORY_ROWS_CACHE_TS[kind] = time.time()
        return {
            "sheet": f"supabase:{result['table']}",
            "rows_saved": len(normalized_rows),
            "deleted": result.get("deleted", 0),
        }

    service = _service()
    title, _ = _ensure_inventory_sheet(service, kind)
    headers = _inventory_headers(kind)
    fields = _inventory_fields(kind)
    values = [headers] + [[row.get(field, "") for field in fields] for row in normalized_rows]

    service.spreadsheets().values().clear(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A2:Z",
        body={},
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=settings.google_sheets_spreadsheet_id,
        range=f"{title}!A1",
        valueInputOption="RAW",
        body={"values": values},
    ).execute()
    _INVENTORY_ROWS_CACHE[kind] = [dict(row) for row in normalized_rows]
    _INVENTORY_ROWS_CACHE_TS[kind] = time.time()

    return {
        "sheet": title,
        "rows_saved": len(normalized_rows),
    }


def _quietpipe_name_matches(text: str) -> bool:
    value = (text or "").strip().lower()
    if not value:
        return False
    aliases = [
        "קוואיטפייפ",
        "קווואיטפייפ",
        "קוויט פייפ",
        "קוויטפייפ",
        "קוויט-פייפ",
        "quietpipe",
        "quit pipe",
        "יריעה אקוסטית",
        "אקוסטיפייפ",
        "אקוסטי פייפ",
    ]
    return any(alias.lower() in value for alias in aliases)


def _quietpipe_quantity_in_units(description: str, quantity, unit: str = "") -> float | None:
    try:
        qty = float(quantity or 0)
    except Exception:
        return None

    if qty <= 0:
        return None

    desc = (description or "").lower()
    unit_value = str(unit or "").strip().lower()
    unit_markers = ["יח'", " יח ", "יחידה", "יחידות"]
    square_meter_markers = ['מ"ר', "מטר מרובע", "מטרים רבועים", "מר"]

    if any(marker in unit_value for marker in unit_markers):
        return qty

    if any(marker in unit_value for marker in square_meter_markers):
        return qty / 2

    if any(marker in desc for marker in unit_markers):
        return qty

    if any(marker in desc for marker in square_meter_markers):
        return qty / 2

    return qty / 2


def deduct_quietpipe_finish_inventory(description: str, quantity, *, unit: str = "", sandbox_run: bool = False, po_number: str = "") -> dict:
    if not _quietpipe_name_matches(description):
        return {"status": "skipped", "reason": "not_quietpipe"}

    quantity_units = _quietpipe_quantity_in_units(description, quantity, unit)
    if quantity_units is None:
        return {"status": "skipped", "reason": "no_quantity"}

    rows = load_inventory_rows("finish")
    if not rows:
        return {"status": "skipped", "reason": "finish_inventory_empty"}

    target_index = None
    for index, row in enumerate(rows):
        if _quietpipe_name_matches(row.get("product", "")):
            target_index = index
            break

    if target_index is None:
        return {"status": "skipped", "reason": "quietpipe_row_missing"}

    current_value_raw = str(rows[target_index].get("actual_quantity", "") or "").strip()
    try:
        current_value = float(current_value_raw) if current_value_raw else 0.0
    except Exception:
        current_value = 0.0

    new_value = current_value - quantity_units
    rows[target_index]["actual_quantity"] = (
        str(int(new_value)) if float(new_value).is_integer() else f"{new_value:.2f}".rstrip("0").rstrip(".")
    )

    save_result = save_inventory_rows("finish", rows)
    result = {
        "status": "ok",
        "product": rows[target_index].get("product", ""),
        "deducted_units": quantity_units,
        "previous_quantity": current_value,
        "new_quantity": new_value,
        "save_result": save_result,
    }
    if sandbox_run:
        sandbox_rows = _load_sandbox_deduction_rows()
        sandbox_rows.append(
            {
                "timestamp": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
                "product": rows[target_index].get("product", ""),
                "deducted_units": (
                    str(int(quantity_units))
                    if float(quantity_units).is_integer()
                    else f"{quantity_units:.2f}".rstrip("0").rstrip(".")
                ),
                "po_number": po_number or "",
                "description": description or "",
                "unit": unit or "",
            }
        )
        result["sandbox_log_result"] = _save_sandbox_deduction_rows(sandbox_rows)
    return result


def restore_sandbox_finish_inventory_deductions() -> dict:
    sandbox_rows = _load_sandbox_deduction_rows()
    if not sandbox_rows:
        return {"status": "skipped", "reason": "no_pending_sandbox_deductions"}

    quietpipe_units = 0.0
    for row in sandbox_rows:
        if _quietpipe_name_matches(row.get("product", "")) or _quietpipe_name_matches(row.get("description", "")):
            try:
                quietpipe_units += float(row.get("deducted_units") or 0)
            except Exception:
                continue

    if quietpipe_units <= 0:
        return {"status": "skipped", "reason": "no_supported_deductions_to_restore", "entries_count": len(sandbox_rows)}

    rows = load_inventory_rows("finish")
    if not rows:
        return {"status": "skipped", "reason": "finish_inventory_empty", "entries_count": len(sandbox_rows)}

    target_index = None
    for index, row in enumerate(rows):
        if _quietpipe_name_matches(row.get("product", "")):
            target_index = index
            break

    if target_index is None:
        return {"status": "skipped", "reason": "quietpipe_row_missing", "entries_count": len(sandbox_rows)}

    current_value_raw = str(rows[target_index].get("actual_quantity", "") or "").strip()
    try:
        current_value = float(current_value_raw) if current_value_raw else 0.0
    except Exception:
        current_value = 0.0

    new_value = current_value + quietpipe_units
    rows[target_index]["actual_quantity"] = (
        str(int(new_value)) if float(new_value).is_integer() else f"{new_value:.2f}".rstrip("0").rstrip(".")
    )

    save_result = save_inventory_rows("finish", rows)
    clear_result = _save_sandbox_deduction_rows([])
    return {
        "status": "ok",
        "product": rows[target_index].get("product", ""),
        "restored_units": quietpipe_units,
        "previous_quantity": current_value,
        "new_quantity": new_value,
        "entries_count": len(sandbox_rows),
        "save_result": save_result,
        "sandbox_log_result": clear_result,
    }


def get_pending_sandbox_finish_inventory_deductions() -> dict:
    sandbox_rows = _load_sandbox_deduction_rows()
    quietpipe_units = 0.0
    for row in sandbox_rows:
        if _quietpipe_name_matches(row.get("product", "")) or _quietpipe_name_matches(row.get("description", "")):
            try:
                quietpipe_units += float(row.get("deducted_units") or 0)
            except Exception:
                continue
    return {
        "entries_count": len(sandbox_rows),
        "quietpipe_units": quietpipe_units,
    }
