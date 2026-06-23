from datetime import datetime
from googleapiclient.discovery import build

from .config import settings
from .google_service_account import build_service_account_credentials
from .models import PurchaseOrderData

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _get_service():
    credentials = build_service_account_credentials(SCOPES)
    return build("sheets", "v4", credentials=credentials)


def _sheet_safe_text(value: str) -> str:
    return value.replace('"', '""').strip()


def _customer_lookup_formula(customer_name: str) -> str:
    name = _sheet_safe_text(customer_name or "")
    return f'=IFERROR(INDEX(FILTER(\'calculator back office\'!N:N,\'calculator back office\'!N:N="{name}"),1),"{name}")'


def _format_amount(value) -> str:
    if value is None:
        return ""
    return f"{float(value):.2f}"


def build_row(po: PurchaseOrderData, delivery_id: str, invoice_id: str, source_pdf_path: Path) -> list[str]:
    return [
        po.po_date or "",                                   # A - תאריך הזמנה
        _customer_lookup_formula(po.customer_name or ""),   # B - שם לקוח לפי calculator back office!N:N
        po.payment_terms_label or "",                       # C - שוטף + X
        "גביה",                                             # D
        _format_amount(po.total),                           # E
        po.po_number or "",                                 # F
        delivery_id or "",                                  # G
        "",                                                 # H
        invoice_id or "",                                   # I
        po.customer_email or "",                            # J
        "automation",                                       # K
        "",                                                 # L
        "",                                                 # M
    ]


def append_purchase_order_row(po: PurchaseOrderData, delivery_id: str, invoice_id: str, source_pdf_path: Path) -> dict:
    service = _get_service()
    values = [build_row(po, delivery_id, invoice_id, source_pdf_path)]

    return (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=settings.google_sheets_spreadsheet_id,
            range=settings.google_sheets_range,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": values},
        )
        .execute()
    )
