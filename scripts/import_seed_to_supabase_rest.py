from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib import error, parse, request


ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "supabase" / "seed" / "current_state"


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _as_bool(value: Any) -> bool | None:
    normalized = _as_str(value).lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    return None


def _as_int(value: Any) -> int | None:
    raw = _as_str(value)
    if not raw:
        return None
    try:
        return int(Decimal(raw))
    except Exception:
        return None


def _as_float(value: Any) -> float | None:
    raw = _as_str(value)
    if not raw:
        return None
    try:
        return float(Decimal(raw))
    except Exception:
        return None


def _as_json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(item).strip() for item in parsed if str(item).strip()]
            except Exception:
                pass
        return [item.strip() for item in raw.split(",") if item.strip()]
    return []


def _raw_payload(row: dict[str, Any]) -> dict[str, Any]:
    return row


def map_customer(row: dict[str, Any], *, force_active: bool | None = None) -> dict[str, Any]:
    return {
        "id": _as_str(row.get("customer_guid")) or _as_str(row.get("customer_id")) or _as_str(row.get("customer_name")),
        "customer_guid": _as_str(row.get("customer_guid")) or None,
        "customer_name": _as_str(row.get("customer_name")),
        "customer_id": _as_str(row.get("customer_id")) or None,
        "source_mode": _as_str(row.get("source_mode")) or None,
        "active": force_active if force_active is not None else (_as_bool(row.get("active")) if _as_bool(row.get("active")) is not None else True),
        "send": _as_bool(row.get("send")),
        "department": _as_str(row.get("department")) or None,
        "accounting_key": _as_str(row.get("accounting_key")) or None,
        "payment_terms_days": _as_int(row.get("payment_terms_days")),
        "phone": _as_str(row.get("phone")) or None,
        "mobile": _as_str(row.get("mobile")) or None,
        "emails": _as_json_list(row.get("emails")),
        "contact_person": _as_str(row.get("contact_person")) or None,
        "address": _as_str(row.get("address")) or None,
        "city": _as_str(row.get("city")) or None,
        "zip": _as_str(row.get("zip")) or None,
        "country": _as_str(row.get("country")) or None,
        "bank_name": _as_str(row.get("bank_name")) or None,
        "bank_branch": _as_str(row.get("bank_branch")) or None,
        "bank_account": _as_str(row.get("bank_account")) or None,
        "remarks": _as_str(row.get("remarks")) or None,
        "income_amount": _as_float(row.get("income_amount")),
        "payment_amount": _as_float(row.get("payment_amount")),
        "balance_amount": _as_float(row.get("balance_amount")),
        "creation_date": _as_str(row.get("creation_date")) or None,
        "last_update_date": _as_str(row.get("last_update_date")) or None,
        "customer_domain": _as_str(row.get("customer_domain")) or None,
        "bank_details_updated_sent": _as_bool(row.get("bank_details_updated_sent")),
        "synced_at": _as_str(row.get("synced_at")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_order_history(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _as_str(row.get("history_id")) or _as_str(row.get("delivery_document_number")) or _as_str(row.get("tax_invoice_number")),
        "history_id": _as_str(row.get("history_id")) or None,
        "created_at_source": _as_str(row.get("created_at")) or None,
        "input_source": _as_str(row.get("input_source")) or None,
        "mode": _as_str(row.get("mode")) or None,
        "customer_name": _as_str(row.get("customer_name")) or None,
        "customer_id": _as_str(row.get("customer_id")) or None,
        "customer_email": _as_str(row.get("customer_email")) or None,
        "customer_phone": _as_str(row.get("customer_phone")) or None,
        "delivery_address": _as_str(row.get("delivery_address")) or None,
        "project": _as_str(row.get("project")) or None,
        "contact_name": _as_str(row.get("contact_name")) or None,
        "contact_phone": _as_str(row.get("contact_phone")) or None,
        "payment_terms_days": _as_int(row.get("payment_terms_days")),
        "payment_terms_label": _as_str(row.get("payment_terms_label")) or None,
        "po_number": _as_str(row.get("po_number")) or None,
        "quote_number": _as_str(row.get("quote_number")) or None,
        "fulfillment_id": _as_str(row.get("fulfillment_id")) or None,
        "document_mode": _as_str(row.get("document_mode")) or None,
        "order_status_tag": _as_str(row.get("order_status_tag")) or None,
        "delivery_document_number": _as_str(row.get("delivery_document_number")) or None,
        "delivery_document_id": _as_str(row.get("delivery_document_id")) or None,
        "tax_invoice_number": _as_str(row.get("tax_invoice_number")) or None,
        "tax_invoice_document_id": _as_str(row.get("tax_invoice_document_id")) or None,
        "item_description": _as_str(row.get("item_description")) or None,
        "item_sku": _as_str(row.get("item_sku")) or None,
        "item_unit": _as_str(row.get("item_unit")) or None,
        "item_quantity": _as_float(row.get("item_quantity")),
        "item_unit_price": _as_float(row.get("item_unit_price")),
        "item_line_total": _as_float(row.get("item_line_total")),
        "subtotal": _as_float(row.get("subtotal")),
        "vat": _as_float(row.get("vat")),
        "total": _as_float(row.get("total")),
        "footer_text": _as_str(row.get("footer_text")) or None,
        "items_json": row.get("items_json"),
        "label_split_rows_json": row.get("label_split_rows_json"),
        "document_links_json": row.get("document_links_json"),
        "drive_payload": {
            "order_drive_folder_id": row.get("order_drive_folder_id"),
            "order_drive_folder_url": row.get("order_drive_folder_url"),
            "delivery_drive_file_id": row.get("delivery_drive_file_id"),
            "invoice_drive_file_id": row.get("invoice_drive_file_id"),
            "merged_drive_file_id": row.get("merged_drive_file_id"),
            "coc_drive_file_id": row.get("coc_drive_file_id"),
        },
        "raw_payload": _raw_payload(row),
    }


def map_quote_history(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _as_str(row.get("history_id")) or _as_str(row.get("quote_number")),
        "history_id": _as_str(row.get("history_id")) or None,
        "created_at_source": _as_str(row.get("created_at")) or None,
        "input_source": _as_str(row.get("input_source")) or None,
        "mode": _as_str(row.get("mode")) or None,
        "customer_name": _as_str(row.get("customer_name")) or None,
        "customer_id": _as_str(row.get("customer_id")) or None,
        "po_number": _as_str(row.get("po_number")) or None,
        "quote_number": _as_str(row.get("quote_number")) or None,
        "quote_document_id": _as_str(row.get("quote_document_id")) or None,
        "quote_date": _as_str(row.get("quote_date")) or None,
        "customer_email": _as_str(row.get("customer_email")) or None,
        "customer_phone": _as_str(row.get("customer_phone")) or None,
        "delivery_address": _as_str(row.get("delivery_address")) or None,
        "project": _as_str(row.get("project")) or None,
        "contact_name": _as_str(row.get("contact_name")) or None,
        "contact_phone": _as_str(row.get("contact_phone")) or None,
        "payment_terms_days": _as_int(row.get("payment_terms_days")),
        "payment_terms_label": _as_str(row.get("payment_terms_label")) or None,
        "item_description": _as_str(row.get("item_description")) or None,
        "item_sku": _as_str(row.get("item_sku")) or None,
        "item_unit": _as_str(row.get("item_unit")) or None,
        "item_quantity": _as_float(row.get("item_quantity")),
        "item_unit_price": _as_float(row.get("item_unit_price")),
        "item_line_total": _as_float(row.get("item_line_total")),
        "subtotal": _as_float(row.get("subtotal")),
        "vat": _as_float(row.get("vat")),
        "total": _as_float(row.get("total")),
        "footer_text": _as_str(row.get("footer_text")) or None,
        "items_json": row.get("items_json"),
        "label_split_rows_json": row.get("label_split_rows_json"),
        "quote_mail_status": _as_str(row.get("quote_mail_status")) or None,
        "quote_mail_sent_at": _as_str(row.get("quote_mail_sent_at")) or None,
        "document_links_json": row.get("document_links_json"),
        "raw_payload": _raw_payload(row),
    }


def map_working_order(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _as_str(row.get("row_id")) or _as_str(row.get("po_number")),
        "row_id": _as_str(row.get("row_id")) or None,
        "created_at_source": _as_str(row.get("created_at")) or None,
        "updated_at_source": _as_str(row.get("updated_at")) or None,
        "source_file_name": _as_str(row.get("source_file_name")) or None,
        "source_file_path": _as_str(row.get("source_file_path")) or None,
        "po_date": _as_str(row.get("po_date")) or None,
        "customer_name": _as_str(row.get("customer_name")) or None,
        "customer_id": _as_str(row.get("customer_id")) or None,
        "customer_email": _as_str(row.get("customer_email")) or None,
        "customer_phone": _as_str(row.get("customer_phone")) or None,
        "delivery_address": _as_str(row.get("delivery_address")) or None,
        "project": _as_str(row.get("project")) or None,
        "contact_name": _as_str(row.get("contact_name")) or None,
        "contact_phone": _as_str(row.get("contact_phone")) or None,
        "payment_terms_days": _as_int(row.get("payment_terms_days")),
        "payment_terms_label": _as_str(row.get("payment_terms_label")) or None,
        "po_number": _as_str(row.get("po_number")) or None,
        "item_description": _as_str(row.get("item_description")) or None,
        "item_sku": _as_str(row.get("item_sku")) or None,
        "item_unit": _as_str(row.get("item_unit")) or None,
        "item_quantity": _as_float(row.get("item_quantity")),
        "item_unit_price": _as_float(row.get("item_unit_price")),
        "subtotal": _as_float(row.get("subtotal")),
        "vat": _as_float(row.get("vat")),
        "total": _as_float(row.get("total")),
        "items_count": _as_int(row.get("items_count")),
        "items_json": row.get("items_json"),
        "payload_json": row.get("payload_json"),
        "drive_payload": {
            "drive_file_id": row.get("drive_file_id"),
            "drive_url": row.get("drive_url"),
            "drive_folder_id": row.get("drive_folder_id"),
            "drive_folder_url": row.get("drive_folder_url"),
            "order_note_drive_file_id": row.get("order_note_drive_file_id"),
            "order_note_drive_url": row.get("order_note_drive_url"),
        },
        "order_note_text": _as_str(row.get("order_note_text")) or None,
        "order_note_file_name": _as_str(row.get("order_note_file_name")) or None,
        "order_note_file_path": _as_str(row.get("order_note_file_path")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_delivery_confirmation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _as_str(row.get("history_id")) or _as_str(row.get("delivery_document_number")) or _as_str(row.get("tax_invoice_number")),
        "history_id": _as_str(row.get("history_id")) or None,
        "order_date": _as_str(row.get("order_date")) or None,
        "company": _as_str(row.get("company")) or None,
        "po_number": _as_str(row.get("po_number")) or None,
        "invoice_date": _as_str(row.get("invoice_date")) or None,
        "tax_invoice_number": _as_str(row.get("tax_invoice_number")) or None,
        "order_total": _as_float(row.get("order_total")),
        "target_email": _as_str(row.get("target_email")) or None,
        "signed_delivery_name": _as_str(row.get("signed_delivery_name")) or None,
        "signed_delivery_local_path": _as_str(row.get("signed_delivery_local_path")) or None,
        "invoice_drive_file_id": _as_str(row.get("invoice_drive_file_id")) or None,
        "coc_name": _as_str(row.get("coc_name")) or None,
        "coc_drive_file_id": _as_str(row.get("coc_drive_file_id")) or None,
        "order_drive_folder_id": _as_str(row.get("order_drive_folder_id")) or None,
        "order_drive_folder_url": _as_str(row.get("order_drive_folder_url")) or None,
        "fulfillment_id": _as_str(row.get("fulfillment_id")) or None,
        "document_mode": _as_str(row.get("document_mode")) or None,
        "delivery_document_number": _as_str(row.get("delivery_document_number")) or None,
        "delivery_document_id": _as_str(row.get("delivery_document_id")) or None,
        "sent": _as_bool(row.get("sent")),
        "sent_at": _as_str(row.get("sent_at")) or None,
        "updated_at_source": _as_str(row.get("updated_at")) or None,
        "source_mode": _as_str(row.get("source_mode")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_delivery_contact(row: dict[str, Any]) -> dict[str, Any]:
    customer_id = _as_str(row.get("customer_id"))
    company = _as_str(row.get("company"))
    email = _as_str(row.get("accounting_email"))
    return {
        "id": customer_id or company or email,
        "company": company or None,
        "customer_id": customer_id or None,
        "accounting_email": email or None,
        "raw_payload": _raw_payload(row),
    }


def map_project_manager(row: dict[str, Any]) -> dict[str, Any]:
    source_key = _as_str(row.get("source_key"))
    company = _as_str(row.get("company"))
    site_address = _as_str(row.get("site_address"))
    contact_name = _as_str(row.get("contact_name"))
    order_date = _as_str(row.get("order_date"))
    item = _as_str(row.get("item"))
    return {
        "id": source_key or "|".join(part for part in [company, site_address, contact_name, order_date, item] if part),
        "company": company or None,
        "tax_id": _as_str(row.get("tax_id")) or None,
        "site_address": site_address or None,
        "contact_name": contact_name or None,
        "order_date": order_date or None,
        "item": item or None,
        "contact_phone": _as_str(row.get("contact_phone")) or None,
        "history_dates": _as_str(row.get("history_dates")) or None,
        "editable_company": _as_str(row.get("editable_company")) or None,
        "editable_tax_id": _as_str(row.get("editable_tax_id")) or None,
        "editable_site_address": _as_str(row.get("editable_site_address")) or None,
        "editable_contact_name": _as_str(row.get("editable_contact_name")) or None,
        "editable_order_date": _as_str(row.get("editable_order_date")) or None,
        "editable_item": _as_str(row.get("editable_item")) or None,
        "editable_contact_phone": _as_str(row.get("editable_contact_phone")) or None,
        "source_key": source_key or None,
        "updated_at_source": _as_str(row.get("updated_at")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_marketing_pipeline(row: dict[str, Any]) -> dict[str, Any]:
    customer_key = _as_str(row.get("customer_key"))
    quote_number = _as_str(row.get("quote_number"))
    quote_document_id = _as_str(row.get("quote_document_id"))
    return {
        "id": customer_key or quote_number or quote_document_id,
        "customer_key": customer_key or None,
        "customer_guid": _as_str(row.get("customer_guid")) or None,
        "customer_id": _as_str(row.get("customer_id")) or None,
        "customer_name": _as_str(row.get("customer_name")) or None,
        "quote_number": quote_number or None,
        "quote_document_id": quote_document_id or None,
        "quote_date": _as_str(row.get("quote_date")) or None,
        "item_name": _as_str(row.get("item_name")) or None,
        "emails": _as_json_list(row.get("emails")),
        "phone": _as_str(row.get("phone")) or None,
        "contact_name": _as_str(row.get("contact_name")) or None,
        "note_text": _as_str(row.get("note_text")) or None,
        "comm_status": _as_str(row.get("comm_status")) or None,
        "comm_sent_at": _as_str(row.get("comm_sent_at")) or None,
        "mail_subject": _as_str(row.get("mail_subject")) or None,
        "mail_sent_at": _as_str(row.get("mail_sent_at")) or None,
        "quote_drive_url": _as_str(row.get("quote_drive_url")) or None,
        "quote_drive_file_id": _as_str(row.get("quote_drive_file_id")) or None,
        "quote_source_url": _as_str(row.get("quote_source_url")) or None,
        "source": _as_str(row.get("source")) or None,
        "updated_at_source": _as_str(row.get("updated_at")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_marketing_work_manager(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _as_str(row.get("row_id"))
    full_name = _as_str(row.get("full_name"))
    company_name = _as_str(row.get("company_name"))
    return {
        "id": row_id or "|".join(part for part in [full_name, company_name, _as_str(row.get("email"))] if part),
        "row_id": row_id or None,
        "full_name": full_name or None,
        "company_name": company_name or None,
        "email": _as_str(row.get("email")) or None,
        "phone_1": _as_str(row.get("phone_1")) or None,
        "phone_2": _as_str(row.get("phone_2")) or None,
        "phone_3": _as_str(row.get("phone_3")) or None,
        "active_status": _as_str(row.get("active_status")) or None,
        "current_employer": _as_str(row.get("current_employer")) or None,
        "current_workplace": _as_str(row.get("current_workplace")) or None,
        "details_url": _as_str(row.get("details_url")) or None,
        "project_manager_match": _as_str(row.get("project_manager_match")) or None,
        "project_manager_checked_at": _as_str(row.get("project_manager_checked_at")) or None,
        "updated_at_source": _as_str(row.get("updated_at")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_marketing_construction_company(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _as_str(row.get("row_id"))
    company_name = _as_str(row.get("company_name"))
    return {
        "id": row_id or company_name,
        "row_id": row_id or None,
        "company_name": company_name or None,
        "company_id": _as_str(row.get("company_id")) or None,
        "phone": _as_str(row.get("phone")) or None,
        "address": _as_str(row.get("address")) or None,
        "email": _as_str(row.get("email")) or None,
        "details_url": _as_str(row.get("details_url")) or None,
        "notes": _as_str(row.get("notes")) or None,
        "updated_at_source": _as_str(row.get("updated_at")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_finance_invoice(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _as_str(row.get("row_id"))
    reference_number = _as_str(row.get("reference_number"))
    return {
        "id": row_id or reference_number,
        "row_id": row_id or None,
        "invoice_date": _as_str(row.get("invoice_date")) or None,
        "supplier_name": _as_str(row.get("supplier_name")) or None,
        "reference_number": reference_number or None,
        "allocation_number": _as_str(row.get("allocation_number")) or None,
        "currency_code": _as_str(row.get("currency_code")) or None,
        "service_or_product": _as_str(row.get("service_or_product")) or None,
        "subtotal": _as_float(row.get("subtotal")),
        "vat": _as_float(row.get("vat")),
        "total": _as_float(row.get("total")),
        "source_file_name": _as_str(row.get("source_file_name")) or None,
        "source_file_path": _as_str(row.get("source_file_path")) or None,
        "report_due_date": _as_str(row.get("report_due_date")) or None,
        "report_due_overrides": row.get("report_due_overrides"),
        "drive_file_id": _as_str(row.get("drive_file_id")) or None,
        "drive_url": _as_str(row.get("drive_url")) or None,
        "updated_at_source": _as_str(row.get("updated_at")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_hr_employee(row: dict[str, Any]) -> dict[str, Any]:
    employee_id = _as_str(row.get("employee_id"))
    return {
        "id": employee_id,
        "employee_id": employee_id,
        "full_name": _as_str(row.get("full_name")) or None,
        "id_number": _as_str(row.get("id_number")) or None,
        "employment_type": _as_str(row.get("employment_type")) or None,
        "active_status": _as_str(row.get("active_status")) or None,
        "start_date": _as_str(row.get("start_date")) or None,
        "base_salary": _as_float(row.get("base_salary")),
        "hourly_rate": _as_float(row.get("hourly_rate")),
        "phone": _as_str(row.get("phone")) or None,
        "email": _as_str(row.get("email")) or None,
        "pension_fund": _as_str(row.get("pension_fund")) or None,
        "notes": _as_str(row.get("notes")) or None,
        "drive_folder_id": _as_str(row.get("drive_folder_id")) or None,
        "drive_folder_url": _as_str(row.get("drive_folder_url")) or None,
        "updated_at_source": _as_str(row.get("updated_at")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_hr_hours(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _as_str(row.get("row_id"))
    return {
        "id": row_id,
        "row_id": row_id,
        "employee_id": _as_str(row.get("employee_id")) or None,
        "employee_name": _as_str(row.get("employee_name")) or None,
        "month_key": _as_str(row.get("month_key")) or None,
        "regular_hours": _as_float(row.get("regular_hours")),
        "overtime_hours": _as_float(row.get("overtime_hours")),
        "hourly_rate": _as_float(row.get("hourly_rate")),
        "status": _as_str(row.get("status")) or None,
        "hours_file_name": _as_str(row.get("hours_file_name")) or None,
        "hours_drive_file_id": _as_str(row.get("hours_drive_file_id")) or None,
        "hours_drive_url": _as_str(row.get("hours_drive_url")) or None,
        "updated_at_source": _as_str(row.get("updated_at")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_hr_payroll(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _as_str(row.get("row_id"))
    return {
        "id": row_id,
        "row_id": row_id,
        "employee_id": _as_str(row.get("employee_id")) or None,
        "employee_name": _as_str(row.get("employee_name")) or None,
        "month_key": _as_str(row.get("month_key")) or None,
        "employment_type": _as_str(row.get("employment_type")) or None,
        "gross_amount": _as_float(row.get("gross_amount")),
        "net_amount": _as_float(row.get("net_amount")),
        "salary_paid": _as_str(row.get("salary_paid")) or None,
        "salary_paid_date": _as_str(row.get("salary_paid_date")) or None,
        "salary_reference": _as_str(row.get("salary_reference")) or None,
        "payslip_file_name": _as_str(row.get("payslip_file_name")) or None,
        "payslip_drive_file_id": _as_str(row.get("payslip_drive_file_id")) or None,
        "payslip_drive_url": _as_str(row.get("payslip_drive_url")) or None,
        "updated_at_source": _as_str(row.get("updated_at")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_hr_document(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _as_str(row.get("row_id"))
    return {
        "id": row_id,
        "row_id": row_id,
        "employee_id": _as_str(row.get("employee_id")) or None,
        "employee_name": _as_str(row.get("employee_name")) or None,
        "category": _as_str(row.get("category")) or None,
        "title": _as_str(row.get("title")) or None,
        "month_key": _as_str(row.get("month_key")) or None,
        "file_name": _as_str(row.get("file_name")) or None,
        "drive_file_id": _as_str(row.get("drive_file_id")) or None,
        "drive_url": _as_str(row.get("drive_url")) or None,
        "updated_at_source": _as_str(row.get("updated_at")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_hr_payslip_prep_history(row: dict[str, Any]) -> dict[str, Any]:
    row_id = _as_str(row.get("row_id"))
    return {
        "id": row_id,
        "row_id": row_id,
        "month_key": _as_str(row.get("month_key")) or None,
        "month_label": _as_str(row.get("month_label")) or None,
        "send_mode": _as_str(row.get("send_mode")) or None,
        "sent_to": _as_str(row.get("sent_to")) or None,
        "sent_at": _as_str(row.get("sent_at")) or None,
        "employees_total": _as_int(row.get("employees_total")),
        "gross_total_label": _as_str(row.get("gross_total_label")) or None,
        "attachments_count": _as_int(row.get("attachments_count")),
        "supporting_summaries_json": row.get("supporting_summaries_json"),
        "notes": _as_str(row.get("notes")) or None,
        "updated_at_source": _as_str(row.get("updated_at")) or None,
        "raw_payload": _raw_payload(row),
    }


def map_raw_only(row: dict[str, Any], *, id_value: str) -> dict[str, Any]:
    return {
        "id": id_value,
        "raw_payload": _raw_payload(row),
    }


DOMAIN_IMPORTS: dict[str, dict[str, Any]] = {
    "customers": {"table": "customers", "mapper": lambda row: map_customer(row, force_active=True), "conflict": "id"},
    "inactive_customers": {"table": "customers", "mapper": lambda row: map_customer(row, force_active=False), "conflict": "id"},
    "order_history": {"table": "order_history", "mapper": map_order_history, "conflict": "id"},
    "quote_history": {"table": "quote_history", "mapper": map_quote_history, "conflict": "id"},
    "working_orders": {"table": "working_orders", "mapper": map_working_order, "conflict": "id"},
    "delivery_confirmations": {"table": "delivery_confirmations", "mapper": map_delivery_confirmation, "conflict": "id"},
    "delivery_contacts": {"table": "delivery_contacts", "mapper": map_delivery_contact, "conflict": "id"},
    "project_managers": {"table": "project_managers", "mapper": map_project_manager, "conflict": "id"},
    "marketing_pipeline": {"table": "marketing_pipeline", "mapper": map_marketing_pipeline, "conflict": "id"},
    "marketing_work_managers": {"table": "marketing_work_managers", "mapper": map_marketing_work_manager, "conflict": "id"},
    "marketing_construction_companies": {"table": "marketing_construction_companies", "mapper": map_marketing_construction_company, "conflict": "id"},
    "finance_invoices": {"table": "finance_invoices", "mapper": map_finance_invoice, "conflict": "id"},
    "hr_employees": {"table": "hr_employees", "mapper": map_hr_employee, "conflict": "id"},
    "hr_hours": {"table": "hr_hours", "mapper": map_hr_hours, "conflict": "id"},
    "hr_payroll": {"table": "hr_payroll", "mapper": map_hr_payroll, "conflict": "id"},
    "hr_documents": {"table": "hr_documents", "mapper": map_hr_document, "conflict": "id"},
    "hr_payslip_prep_history": {"table": "hr_payslip_prep_history", "mapper": map_hr_payslip_prep_history, "conflict": "id"},
    "marketing_history": {"table": "marketing_history", "mapper": lambda row: map_raw_only(row, id_value=_as_str(row.get("row_id")) or _as_str(row.get("customer_key")) or _as_str(row.get("updated_at"))), "conflict": "id"},
    "marketing_reminders": {"table": "marketing_reminders", "mapper": lambda row: map_raw_only(row, id_value=_as_str(row.get("row_id")) or _as_str(row.get("customer_key")) or _as_str(row.get("updated_at"))), "conflict": "id"},
    "finance_customer_withholdings": {"table": "finance_customer_withholdings", "mapper": lambda row: map_raw_only(row, id_value=_as_str(row.get("row_id")) or _as_str(row.get("invoice_number")) or _as_str(row.get("receipt_number")) or _as_str(row.get("updated_at"))), "conflict": "id"},
    "finance_bank_movements": {"table": "finance_bank_movements", "mapper": lambda row: map_raw_only(row, id_value=_as_str(row.get("row_id")) or _as_str(row.get("reference")) or _as_str(row.get("date")) + "|" + _as_str(row.get("amount"))), "conflict": "id"},
    "hr_contributions": {"table": "hr_contributions", "mapper": lambda row: map_raw_only(row, id_value=_as_str(row.get("row_id")) or _as_str(row.get("employee_id")) + "|" + _as_str(row.get("month_key")) + "|" + _as_str(row.get("updated_at"))), "conflict": "id"},
    "payments_transfer": {"table": "payments_transfer_snapshots", "mapper": lambda row: {"id": "current", "current_sheet": row.get("current_sheet"), "sheet_names": row.get("sheet_names"), "recent_rows": row.get("recent_rows"), "historical_rows": row.get("historical_rows"), "all_rows": row.get("all_rows"), "raw_payload": _raw_payload(row)}, "conflict": "id"},
}


def load_seed(domain: str) -> list[dict[str, Any]]:
    path = SEED_DIR / f"{domain}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, list) else [payload]


def request_json(url: str, method: str, headers: dict[str, str], payload: list[dict[str, Any]]) -> tuple[int, str]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, method=method)
    for key, value in headers.items():
        req.add_header(key, value)
    try:
        with request.urlopen(req, timeout=120) as response:
            return response.status, response.read().decode("utf-8")
    except error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8")


def dedupe_rows(rows: list[dict[str, Any]], domain: str) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for row in rows:
        row_id = _as_str(row.get("id"))
        if row_id in deduped:
            duplicate_count += 1
        deduped[row_id] = row
    if duplicate_count:
        print(f"{domain}: collapsed {duplicate_count} duplicate row(s) by id before import")
    return list(deduped.values())


def import_domain(base_url: str, api_key: str, domain: str, chunk_size: int) -> dict[str, Any]:
    config = DOMAIN_IMPORTS[domain]
    rows = load_seed(domain)
    mapped_rows = [config["mapper"](row) for row in rows]
    mapped_rows = [row for row in mapped_rows if row.get("id")]
    mapped_rows = dedupe_rows(mapped_rows, domain)
    endpoint = (
        f"{base_url.rstrip('/')}/rest/v1/{config['table']}"
        f"?on_conflict={parse.quote(config['conflict'])}"
    )
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
        "Content-Profile": "public",
    }

    imported = 0
    for start in range(0, len(mapped_rows), chunk_size):
        chunk = mapped_rows[start:start + chunk_size]
        status, response_text = request_json(endpoint, "POST", headers, chunk)
        if status >= 300:
            raise RuntimeError(f"{domain} chunk starting at {start} failed: HTTP {status}: {response_text}")
        imported += len(chunk)
        print(f"{domain}: imported {imported}/{len(mapped_rows)}")

    return {
        "domain": domain,
        "table": config["table"],
        "rows": len(mapped_rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Import local seed files into Supabase via REST upsert.")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--chunk-size", type=int, default=100)
    parser.add_argument(
        "--domains",
        nargs="+",
        default=list(DOMAIN_IMPORTS.keys()),
        choices=list(DOMAIN_IMPORTS.keys()),
    )
    args = parser.parse_args()

    summary = []
    for domain in args.domains:
        summary.append(import_domain(args.base_url, args.api_key, domain, args.chunk_size))

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
