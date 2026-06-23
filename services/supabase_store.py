from __future__ import annotations

import hashlib
import json
from typing import Any, Callable
from urllib import error, parse, request

from .config import settings

JsonDict = dict[str, Any]


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        if raw.startswith("[") and raw.endswith("]"):
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [item.strip() for item in raw.split(",") if item.strip()]
    return []


def _id_customer(row: JsonDict) -> str:
    return _as_str(row.get("customer_guid")) or _as_str(row.get("customer_id")) or _as_str(row.get("customer_name"))


def _id_order_history(row: JsonDict) -> str:
    return _as_str(row.get("history_id")) or _as_str(row.get("delivery_document_number")) or _as_str(row.get("tax_invoice_number"))


def _id_quote_history(row: JsonDict) -> str:
    return _as_str(row.get("history_id")) or _as_str(row.get("quote_number"))


def _id_working_order(row: JsonDict) -> str:
    return _as_str(row.get("row_id")) or _as_str(row.get("po_number"))


def _id_delivery_confirmation(row: JsonDict) -> str:
    return _as_str(row.get("history_id")) or _as_str(row.get("delivery_document_number")) or _as_str(row.get("tax_invoice_number"))


def _id_delivery_contact(row: JsonDict) -> str:
    return _as_str(row.get("customer_id")) or _as_str(row.get("company")) or _as_str(row.get("accounting_email")) or _as_str(row.get("email"))


def _id_project_manager(row: JsonDict) -> str:
    source_key = _as_str(row.get("source_key"))
    if source_key:
        return source_key
    parts = [
        _as_str(row.get("company")),
        _as_str(row.get("site_address")),
        _as_str(row.get("contact_name")),
        _as_str(row.get("order_date")),
        _as_str(row.get("item")),
    ]
    return "|".join(part for part in parts if part)


def _id_marketing_pipeline(row: JsonDict) -> str:
    return _as_str(row.get("customer_key")) or _as_str(row.get("quote_number")) or _as_str(row.get("quote_document_id"))


def _id_marketing_history(row: JsonDict) -> str:
    return _as_str(row.get("history_id")) or _as_str(row.get("row_id")) or _as_str(row.get("customer_key")) or _as_str(row.get("updated_at"))


def _id_marketing_reminder(row: JsonDict) -> str:
    return _as_str(row.get("reminder_id")) or _as_str(row.get("row_id")) or _as_str(row.get("customer_key")) or _as_str(row.get("updated_at"))


def _id_marketing_work_manager(row: JsonDict) -> str:
    row_id = _as_str(row.get("row_id"))
    if row_id:
        return row_id
    parts = [_as_str(row.get("full_name")), _as_str(row.get("company_name")), _as_str(row.get("email"))]
    return "|".join(part for part in parts if part)


def _id_marketing_construction_company(row: JsonDict) -> str:
    return _as_str(row.get("row_id")) or _as_str(row.get("company_name"))


def _id_finance_invoice(row: JsonDict) -> str:
    return _as_str(row.get("row_id")) or _as_str(row.get("reference_number"))


def _id_finance_withholding(row: JsonDict) -> str:
    return _as_str(row.get("row_id")) or _as_str(row.get("invoice_number")) or _as_str(row.get("receipt_number")) or _as_str(row.get("updated_at"))


def _id_finance_bank_movement(row: JsonDict) -> str:
    return _as_str(row.get("row_id")) or _as_str(row.get("reference")) or f"{_as_str(row.get('transaction_date') or row.get('date'))}|{_as_str(row.get('amount'))}"


def _id_hr_employee(row: JsonDict) -> str:
    return _as_str(row.get("employee_id"))


def _id_hr_hours(row: JsonDict) -> str:
    return _as_str(row.get("row_id")) or f"{_as_str(row.get('employee_id'))}|{_as_str(row.get('month_key'))}|{_as_str(row.get('updated_at'))}"


def _id_hr_payroll(row: JsonDict) -> str:
    return _as_str(row.get("row_id")) or f"{_as_str(row.get('employee_id'))}|{_as_str(row.get('month_key'))}|{_as_str(row.get('updated_at'))}"


def _id_hr_contribution(row: JsonDict) -> str:
    return _as_str(row.get("row_id")) or f"{_as_str(row.get('employee_id'))}|{_as_str(row.get('month_key'))}|{_as_str(row.get('updated_at'))}"


def _id_hr_document(row: JsonDict) -> str:
    return _as_str(row.get("row_id")) or f"{_as_str(row.get('employee_id'))}|{_as_str(row.get('category'))}|{_as_str(row.get('month_key'))}|{_as_str(row.get('updated_at'))}"


def _id_hr_prep_history(row: JsonDict) -> str:
    return _as_str(row.get("row_id")) or f"{_as_str(row.get('month_key'))}|{_as_str(row.get('sent_at'))}|{_as_str(row.get('updated_at'))}"


def _id_finance_setting(row: JsonDict) -> str:
    return _as_str(row.get("setting_key"))


def _id_payments_transfer_state(row: JsonDict) -> str:
    return _as_str(row.get("id")) or "current"


def _stable_row_hash(prefix: str, row: JsonDict) -> str:
    payload = json.dumps(row or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:{hashlib.sha1(payload.encode('utf-8')).hexdigest()}"


def _id_pazomat(row: JsonDict) -> str:
    return _as_str(row.get("month")) or _as_str(row.get("invoice_number")) or _stable_row_hash("pazomat", row)


def _id_sibus(row: JsonDict) -> str:
    return _as_str(row.get("month")) or _as_str(row.get("invoice_number")) or _stable_row_hash("sibus", row)


def _id_supplier_delivery_note(row: JsonDict) -> str:
    return (
        _as_str(row.get("record_id"))
        or "|".join(
            part for part in [
                _as_str(row.get("delivery_note_number")),
                _as_str(row.get("item_index")),
                _as_str(row.get("source_document_name")),
            ] if part
        )
        or _stable_row_hash("supplier_delivery_note", row)
    )


def _id_inventory_purchase_order(row: JsonDict) -> str:
    return (
        _as_str(row.get("history_id"))
        or _as_str(row.get("po_document_id"))
        or "|".join(part for part in [_as_str(row.get("po_number")), _as_str(row.get("created_at"))] if part)
        or _stable_row_hash("inventory_purchase_order", row)
    )


def _id_pricing_item(row: JsonDict) -> str:
    return _as_str(row.get("item_id")) or _stable_row_hash("pricing_item", row)


def _id_pricing_component(row: JsonDict) -> str:
    return _as_str(row.get("component_id")) or _stable_row_hash("pricing_component", row)


def _id_inventory_raw(row: JsonDict) -> str:
    return (
        _as_str(row.get("_row_id"))
        or "|".join(
            part for part in [
                _as_str(row.get("supplier")),
                _as_str(row.get("supplier_sku")),
                _as_str(row.get("product")),
                _as_str(row.get("material")),
                _as_str(row.get("length")),
                _as_str(row.get("width")),
                _as_str(row.get("thickness")),
                _as_str(row.get("unit")),
            ] if part
        )
        or _stable_row_hash("inventory_raw", row)
    )


def _id_inventory_finish(row: JsonDict) -> str:
    return (
        _as_str(row.get("_row_id"))
        or "|".join(
            part for part in [
                _as_str(row.get("product")),
                _as_str(row.get("width")),
                _as_str(row.get("length")),
            ] if part
        )
        or _stable_row_hash("inventory_finish", row)
    )


def _id_inventory_contact(row: JsonDict) -> str:
    return (
        _as_str(row.get("_row_id"))
        or "|".join(
            part for part in [
                _as_str(row.get("company")),
                _as_str(row.get("name")),
                _as_str(row.get("email")),
                _as_str(row.get("direct_phone")),
            ] if part
        )
        or _stable_row_hash("inventory_contact", row)
    )


def _map_customer(row: JsonDict, *, active: bool) -> JsonDict:
    return {
        "id": _id_customer(row),
        "customer_guid": _as_str(row.get("customer_guid")) or None,
        "customer_name": _as_str(row.get("customer_name")) or None,
        "customer_id": _as_str(row.get("customer_id")) or None,
        "source_mode": _as_str(row.get("source_mode")) or None,
        "active": active,
        "send": str(row.get("send", "")).strip().lower() in {"1", "true", "yes", "on"},
        "department": _as_str(row.get("department")) or None,
        "accounting_key": _as_str(row.get("accounting_key")) or None,
        "payment_terms_days": int(_as_str(row.get("payment_terms_days")) or "0") if _as_str(row.get("payment_terms_days")) else None,
        "phone": _as_str(row.get("phone")) or None,
        "mobile": _as_str(row.get("mobile")) or None,
        "emails": _json_list(row.get("emails")),
        "contact_person": _as_str(row.get("contact_person")) or None,
        "address": _as_str(row.get("address")) or None,
        "city": _as_str(row.get("city")) or None,
        "zip": _as_str(row.get("zip")) or None,
        "country": _as_str(row.get("country")) or None,
        "bank_name": _as_str(row.get("bank_name")) or None,
        "bank_branch": _as_str(row.get("bank_branch")) or None,
        "bank_account": _as_str(row.get("bank_account")) or None,
        "remarks": _as_str(row.get("remarks")) or None,
        "creation_date": _as_str(row.get("creation_date")) or None,
        "last_update_date": _as_str(row.get("last_update_date")) or None,
        "customer_domain": _as_str(row.get("customer_domain")) or None,
        "bank_details_updated_sent": str(row.get("bank_details_updated_sent", "")).strip().lower() in {"1", "true", "yes", "on"},
        "synced_at": _as_str(row.get("synced_at")) or None,
        "raw_payload": row,
    }


def _map_raw(row: JsonDict, row_id: str) -> JsonDict:
    return {"id": row_id, "raw_payload": row}


def _map_finance_setting(row: JsonDict) -> JsonDict:
    setting_key = _id_finance_setting(row)
    return {
        "key": setting_key,
        "value": dict(row),
    }


def _map_payments_transfer_state(row: JsonDict) -> JsonDict:
    snapshot_id = _id_payments_transfer_state(row)
    payload = dict(row)
    payload["id"] = snapshot_id
    return {
        "id": snapshot_id,
        "current_sheet": _as_str(payload.get("current_sheet")) or None,
        "sheet_names": payload.get("sheet_names") if isinstance(payload.get("sheet_names"), list) else [],
        "recent_rows": payload.get("recent_rows") if isinstance(payload.get("recent_rows"), list) else [],
        "historical_rows": payload.get("historical_rows") if isinstance(payload.get("historical_rows"), list) else [],
        "all_rows": payload.get("all_rows") if isinstance(payload.get("all_rows"), list) else [],
        "raw_payload": payload,
    }


def _decode_raw_payload(item: JsonDict) -> JsonDict | None:
    raw_payload = item.get("raw_payload") if isinstance(item, dict) else None
    if isinstance(raw_payload, dict):
        return raw_payload
    return None


def _decode_finance_setting(item: JsonDict) -> JsonDict | None:
    if not isinstance(item, dict):
        return None
    key = _as_str(item.get("key"))
    value = item.get("value")
    if isinstance(value, dict):
        row = dict(value)
        row["setting_key"] = _as_str(row.get("setting_key")) or key
        if not row.get("updated_at") and _as_str(item.get("updated_at")):
            row["updated_at"] = _as_str(item.get("updated_at"))
        return row
    if not key:
        return None
    return {
        "setting_key": key,
        "setting_value": _as_str(value),
        "updated_at": _as_str(item.get("updated_at")),
    }


def _map_keyed_app_state(setting_key: str, row: JsonDict) -> JsonDict:
    return {
        "key": setting_key,
        "value": dict(row or {}),
    }


def _decode_keyed_app_state(item: JsonDict) -> JsonDict | None:
    if not isinstance(item, dict):
        return None
    value = item.get("value")
    if isinstance(value, dict):
        row = dict(value)
        row.setdefault("setting_key", _as_str(item.get("key")))
        if not row.get("updated_at") and _as_str(item.get("updated_at")):
            row["updated_at"] = _as_str(item.get("updated_at"))
        return row
    return None


def _app_state_config(setting_key: str) -> JsonDict:
    return {
        "table": "app_settings",
        "pk_field": "key",
        "select": "key,value,updated_at",
        "filter": {"key": f"eq.{setting_key}"},
        "id_getter": lambda _row, _setting_key=setting_key: _setting_key,
        "mapper": lambda row, _setting_key=setting_key: _map_keyed_app_state(_setting_key, row),
        "decoder": _decode_keyed_app_state,
    }


TABLE_CONFIGS: dict[str, JsonDict] = {
    "customers": {
        "table": "customers",
        "id_getter": _id_customer,
        "filter": {"active": "eq.true"},
        "mapper": lambda row: _map_customer(row, active=True),
    },
    "inactive_customers": {
        "table": "customers",
        "id_getter": _id_customer,
        "filter": {"active": "eq.false"},
        "mapper": lambda row: _map_customer(row, active=False),
    },
    "order_history": {"table": "order_history", "id_getter": _id_order_history, "mapper": lambda row: _map_raw(row, _id_order_history(row))},
    "quote_history": {"table": "quote_history", "id_getter": _id_quote_history, "mapper": lambda row: _map_raw(row, _id_quote_history(row))},
    "working_orders": {"table": "working_orders", "id_getter": _id_working_order, "mapper": lambda row: _map_raw(row, _id_working_order(row))},
    "delivery_confirmations": {"table": "delivery_confirmations", "id_getter": _id_delivery_confirmation, "mapper": lambda row: _map_raw(row, _id_delivery_confirmation(row))},
    "delivery_contacts": {"table": "delivery_contacts", "id_getter": _id_delivery_contact, "mapper": lambda row: _map_raw(row, _id_delivery_contact(row))},
    "project_managers": {"table": "project_managers", "id_getter": _id_project_manager, "mapper": lambda row: _map_raw(row, _id_project_manager(row))},
    "marketing_pipeline": {"table": "marketing_pipeline", "id_getter": _id_marketing_pipeline, "mapper": lambda row: _map_raw(row, _id_marketing_pipeline(row))},
    "marketing_history": {"table": "marketing_history", "id_getter": _id_marketing_history, "mapper": lambda row: _map_raw(row, _id_marketing_history(row))},
    "marketing_reminders": {"table": "marketing_reminders", "id_getter": _id_marketing_reminder, "mapper": lambda row: _map_raw(row, _id_marketing_reminder(row))},
    "marketing_work_managers": {"table": "marketing_work_managers", "id_getter": _id_marketing_work_manager, "mapper": lambda row: _map_raw(row, _id_marketing_work_manager(row))},
    "marketing_construction_companies": {"table": "marketing_construction_companies", "id_getter": _id_marketing_construction_company, "mapper": lambda row: _map_raw(row, _id_marketing_construction_company(row))},
    "finance_invoices": {"table": "finance_invoices", "id_getter": _id_finance_invoice, "mapper": lambda row: _map_raw(row, _id_finance_invoice(row))},
    "finance_settings": {
        "table": "app_settings",
        "pk_field": "key",
        "select": "key,value,updated_at",
        "id_getter": _id_finance_setting,
        "mapper": _map_finance_setting,
        "decoder": _decode_finance_setting,
    },
    "app_hidden_marketing_pipeline_keys": _app_state_config("app_hidden_marketing_pipeline_keys"),
    "app_hidden_customer_keys": _app_state_config("app_hidden_customer_keys"),
    "app_inventory_purchase_order_hidden_keys": _app_state_config("app_inventory_purchase_order_hidden_keys"),
    "app_delivery_confirmation_suppressions": _app_state_config("app_delivery_confirmation_suppressions"),
    "app_marketing_pipeline_quote_updates": _app_state_config("app_marketing_pipeline_quote_updates"),
    "app_payments_receipt_sync_meta": _app_state_config("app_payments_receipt_sync_meta"),
    "app_manual_order_recent_customers": _app_state_config("app_manual_order_recent_customers"),
    "app_auth_state": _app_state_config("app_auth_state"),
    "app_gmail_oauth_token": _app_state_config("app_gmail_oauth_token"),
    "app_google_drive_oauth_token": _app_state_config("app_google_drive_oauth_token"),
    "finance_customer_withholdings": {"table": "finance_customer_withholdings", "id_getter": _id_finance_withholding, "mapper": lambda row: _map_raw(row, _id_finance_withholding(row))},
    "finance_bank_movements": {"table": "finance_bank_movements", "id_getter": _id_finance_bank_movement, "mapper": lambda row: _map_raw(row, _id_finance_bank_movement(row))},
    "payments_transfer_state": {
        "table": "payments_transfer_snapshots",
        "id_getter": _id_payments_transfer_state,
        "mapper": _map_payments_transfer_state,
        "decoder": _decode_raw_payload,
    },
    "pazomat": {"table": "pazomat", "id_getter": _id_pazomat, "mapper": lambda row: _map_raw(row, _id_pazomat(row))},
    "sibus": {"table": "sibus", "id_getter": _id_sibus, "mapper": lambda row: _map_raw(row, _id_sibus(row))},
    "supplier_delivery_notes": {
        "table": "supplier_delivery_notes",
        "id_getter": _id_supplier_delivery_note,
        "mapper": lambda row: _map_raw(row, _id_supplier_delivery_note(row)),
    },
    "inventory_purchase_orders": {
        "table": "inventory_purchase_orders",
        "id_getter": _id_inventory_purchase_order,
        "mapper": lambda row: _map_raw(row, _id_inventory_purchase_order(row)),
    },
    "pricing_items": {
        "table": "pricing_items",
        "id_getter": _id_pricing_item,
        "mapper": lambda row: _map_raw(row, _id_pricing_item(row)),
    },
    "pricing_components": {
        "table": "pricing_components",
        "id_getter": _id_pricing_component,
        "mapper": lambda row: _map_raw(row, _id_pricing_component(row)),
    },
    "inventory_raw": {
        "table": "inventory_raw",
        "id_getter": _id_inventory_raw,
        "mapper": lambda row: _map_raw(row, _id_inventory_raw(row)),
    },
    "inventory_finish": {
        "table": "inventory_finish",
        "id_getter": _id_inventory_finish,
        "mapper": lambda row: _map_raw(row, _id_inventory_finish(row)),
    },
    "inventory_contacts": {
        "table": "inventory_contacts",
        "id_getter": _id_inventory_contact,
        "mapper": lambda row: _map_raw(row, _id_inventory_contact(row)),
    },
    "hr_employees": {"table": "hr_employees", "id_getter": _id_hr_employee, "mapper": lambda row: _map_raw(row, _id_hr_employee(row))},
    "hr_hours": {"table": "hr_hours", "id_getter": _id_hr_hours, "mapper": lambda row: _map_raw(row, _id_hr_hours(row))},
    "hr_payroll": {"table": "hr_payroll", "id_getter": _id_hr_payroll, "mapper": lambda row: _map_raw(row, _id_hr_payroll(row))},
    "hr_contributions": {"table": "hr_contributions", "id_getter": _id_hr_contribution, "mapper": lambda row: _map_raw(row, _id_hr_contribution(row))},
    "hr_documents": {"table": "hr_documents", "id_getter": _id_hr_document, "mapper": lambda row: _map_raw(row, _id_hr_document(row))},
    "hr_payslip_prep_history": {"table": "hr_payslip_prep_history", "id_getter": _id_hr_prep_history, "mapper": lambda row: _map_raw(row, _id_hr_prep_history(row))},
}


def is_enabled() -> bool:
    return (
        str(settings.data_backend or "").strip().lower() == "supabase"
        and bool(str(settings.supabase_url or "").strip())
        and bool(str(settings.supabase_service_role_key or "").strip())
    )


def supports_domain(domain: str) -> bool:
    return domain in TABLE_CONFIGS


def _base_headers(*, write: bool) -> dict[str, str]:
    api_key = str(settings.supabase_service_role_key or "").strip()
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
    }
    if write:
        headers["Content-Type"] = "application/json"
        headers["Content-Profile"] = settings.supabase_schema
    else:
        headers["Accept-Profile"] = settings.supabase_schema
    return headers


def _request_json(method: str, path: str, *, payload: Any | None = None, headers: dict[str, str] | None = None) -> Any:
    url = f"{str(settings.supabase_url).rstrip('/')}{path}"
    body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, method=method.upper())
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with request.urlopen(req, timeout=120) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return None
            return json.loads(raw)
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8")
        raise RuntimeError(f"Supabase {method.upper()} {path} failed with HTTP {exc.code}: {details}") from exc


def _query_string(params: dict[str, str]) -> str:
    return "&".join(f"{parse.quote(key)}={parse.quote(value)}" for key, value in params.items())


def _config(domain: str) -> JsonDict:
    try:
        return TABLE_CONFIGS[domain]
    except KeyError as exc:
        raise ValueError(f"Unsupported Supabase domain: {domain}") from exc


def fetch_domain_rows(domain: str) -> list[JsonDict]:
    config = _config(domain)
    pk_field = _as_str(config.get("pk_field")) or "id"
    decoder: Callable[[JsonDict], JsonDict | None] = config.get("decoder") or _decode_raw_payload
    select_fields = _as_str(config.get("select")) or f"{pk_field},raw_payload"
    base_params = {"select": select_fields, **(config.get("filter") or {})}
    offset = 0
    limit = 1000
    rows: list[JsonDict] = []
    while True:
        params = {**base_params, "order": f"{pk_field}.asc", "offset": str(offset), "limit": str(limit)}
        payload = _request_json(
            "GET",
            f"/rest/v1/{config['table']}?{_query_string(params)}",
            headers=_base_headers(write=False),
        )
        chunk = payload if isinstance(payload, list) else []
        for item in chunk:
            decoded = decoder(item) if isinstance(item, dict) else None
            if isinstance(decoded, dict):
                rows.append(decoded)
        if len(chunk) < limit:
            break
        offset += limit
    return rows


def _fetch_existing_ids(domain: str) -> list[str]:
    config = _config(domain)
    pk_field = _as_str(config.get("pk_field")) or "id"
    base_params = {"select": pk_field, **(config.get("filter") or {})}
    offset = 0
    limit = 1000
    ids: list[str] = []
    while True:
        params = {**base_params, "order": f"{pk_field}.asc", "offset": str(offset), "limit": str(limit)}
        payload = _request_json(
            "GET",
            f"/rest/v1/{config['table']}?{_query_string(params)}",
            headers=_base_headers(write=False),
        )
        chunk = payload if isinstance(payload, list) else []
        for item in chunk:
            row_id = _as_str(item.get(pk_field)) if isinstance(item, dict) else ""
            if row_id:
                ids.append(row_id)
        if len(chunk) < limit:
            break
        offset += limit
    return ids


def _delete_row(domain: str, row_id: str) -> None:
    config = _config(domain)
    pk_field = _as_str(config.get("pk_field")) or "id"
    params = {**(config.get("filter") or {}), pk_field: f"eq.{row_id}"}
    _request_json(
        "DELETE",
        f"/rest/v1/{config['table']}?{_query_string(params)}",
        headers={**_base_headers(write=True), "Prefer": "return=minimal"},
    )


def replace_domain_rows(domain: str, rows: list[JsonDict]) -> dict[str, Any]:
    config = _config(domain)
    mapper: Callable[[JsonDict], JsonDict] = config["mapper"]
    pk_field = _as_str(config.get("pk_field")) or "id"
    mapped_by_id: dict[str, JsonDict] = {}
    for row in rows or []:
        mapped = mapper(dict(row))
        row_id = _as_str(mapped.get(pk_field))
        if not row_id:
            continue
        mapped[pk_field] = row_id
        mapped_by_id[row_id] = mapped

    mapped_rows = list(mapped_by_id.values())
    existing_ids = set(_fetch_existing_ids(domain))
    incoming_ids = set(mapped_by_id)

    chunk_size = 200
    for start in range(0, len(mapped_rows), chunk_size):
        chunk = mapped_rows[start:start + chunk_size]
        if not chunk:
            continue
        _request_json(
            "POST",
            f"/rest/v1/{config['table']}?on_conflict={pk_field}",
            payload=chunk,
            headers={
                **_base_headers(write=True),
                "Prefer": "resolution=merge-duplicates,return=minimal",
            },
        )

    for stale_id in sorted(existing_ids - incoming_ids):
        _delete_row(domain, stale_id)

    return {
        "table": config["table"],
        "rows_saved": len(mapped_rows),
        "deleted": len(existing_ids - incoming_ids),
    }
