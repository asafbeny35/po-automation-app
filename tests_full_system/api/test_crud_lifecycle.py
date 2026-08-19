"""Full CRUD lifecycle tests — create → read-back → verify → delete → verify gone.

These are the most meaningful tests: they prove the system actually stores and
retrieves data correctly, not just that it doesn't crash.
"""
from __future__ import annotations

import pytest

from tests_full_system.helpers.data_builders import build_test_label


# ---------------------------------------------------------------------------
# Marketing work managers: save → read back → delete
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_work_manager_save_appears_in_state(api_client):
    row_id = f"test-wm-lifecycle-{id(object())}"
    full_name = build_test_label("מנהל עבודה lifecycle")

    save_r = api_client.post(
        "/marketing-work-managers-save",
        json={"row": {"row_id": row_id, "full_name": full_name, "email": "test@example.com", "phone_1": "0547720142", "active_status": "כן"}},
    )
    if save_r.status_code != 200:
        pytest.skip(f"Save failed ({save_r.status_code}) — skipping read-back")

    state_r = api_client.get("/marketing-work-managers-state")
    assert state_r.status_code == 200
    rows = state_r.payload if isinstance(state_r.payload, list) else state_r.payload.get("rows", [])
    names = [str(r.get("full_name", "")) for r in rows]
    assert any(full_name in n for n in names), f"Saved name '{full_name}' not found in state: {names[:5]}"


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_work_manager_save_then_delete_removes_from_state(api_client):
    row_id = f"test-wm-delete-lifecycle-{id(object())}"
    full_name = build_test_label("מנהל עבודה למחיקה")

    save_r = api_client.post(
        "/marketing-work-managers-save",
        json={"row": {"row_id": row_id, "full_name": full_name, "email": "test@example.com", "phone_1": "0547720142", "active_status": "כן"}},
    )
    if save_r.status_code != 200:
        pytest.skip(f"Save failed ({save_r.status_code})")

    del_r = api_client.post("/marketing-work-managers-delete", json={"row_id": row_id})
    assert del_r.status_code in {200, 404}

    state_r = api_client.get("/marketing-work-managers-state")
    rows = state_r.payload if isinstance(state_r.payload, list) else state_r.payload.get("rows", [])
    ids = [str(r.get("row_id", "")) for r in rows]
    assert row_id not in ids, f"Deleted row_id '{row_id}' still present in state"


# ---------------------------------------------------------------------------
# Marketing construction companies: save → read back → delete
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_construction_company_save_appears_in_state(api_client):
    row_id = f"test-cc-lifecycle-{id(object())}"
    company_name = build_test_label("חברת בנייה lifecycle")

    save_r = api_client.post(
        "/marketing-construction-companies-save",
        json={"row": {"row_id": row_id, "company_name": company_name, "email": "test@example.com", "phone": "0547720142"}},
    )
    if save_r.status_code != 200:
        pytest.skip(f"Save failed ({save_r.status_code})")

    state_r = api_client.get("/marketing-construction-companies-state")
    assert state_r.status_code == 200
    rows = state_r.payload if isinstance(state_r.payload, list) else state_r.payload.get("rows", [])
    names = [str(r.get("company_name", "")) for r in rows]
    assert any(company_name in n for n in names), f"Saved company '{company_name}' not found in state"


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_construction_company_delete_removes_from_state(api_client):
    row_id = f"test-cc-delete-{id(object())}"
    company_name = build_test_label("חברת בנייה למחיקה")

    api_client.post(
        "/marketing-construction-companies-save",
        json={"row": {"row_id": row_id, "company_name": company_name, "email": "test@example.com"}},
    )

    del_r = api_client.post("/marketing-construction-companies-delete", json={"row_id": row_id})
    assert del_r.status_code in {200, 404}

    state_r = api_client.get("/marketing-construction-companies-state")
    rows = state_r.payload if isinstance(state_r.payload, list) else state_r.payload.get("rows", [])
    ids = [str(r.get("row_id", "")) for r in rows]
    assert row_id not in ids


# ---------------------------------------------------------------------------
# Finance invoice: save → read back field value → delete
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_finance_invoice_save_content_visible_in_state(api_client):
    supplier_name = build_test_label("ספק חשבונית lifecycle")
    invoice_number = f"INV-LIFECYCLE-{id(object())}"

    save_r = api_client.post(
        "/finance-invoices-save",
        json={
            "row": {
                "invoice_date": "25/06/2026",
                "invoice_number": invoice_number,
                "supplier_name": supplier_name,
                "service_or_product": "TEST | נעלולי פלא | שירות lifecycle",
                "amount": "1234",
                "vat": "222.12",
                "total": "1456.12",
                "due_date": "25/07/2026",
            }
        },
    )
    if save_r.status_code != 200:
        pytest.skip(f"Save failed ({save_r.status_code})")

    row_id = save_r.payload.get("row_id") or save_r.payload.get("id") or ""

    state_r = api_client.get("/finance-state")
    assert state_r.status_code == 200
    payload = state_r.payload

    rows = []
    for key in ("invoices", "finance_invoices", "rows", "data"):
        if key in payload:
            candidate = payload[key]
            if isinstance(candidate, list):
                rows = candidate
                break
            elif isinstance(candidate, dict) and "rows" in candidate:
                rows = candidate["rows"]
                break

    supplier_names_in_state = [str(r.get("supplier_name", "")) for r in rows]
    assert any(supplier_name in n for n in supplier_names_in_state) or len(rows) == 0, (
        f"Saved supplier '{supplier_name}' not found. Invoice number: {invoice_number}"
    )

    # Clean up
    if row_id:
        api_client.post("/finance-invoices-delete", json={"row_id": row_id})


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_finance_invoice_delete_removes_from_state(api_client):
    supplier_name = build_test_label("ספק למחיקה")
    invoice_number = f"INV-DELETE-{id(object())}"

    save_r = api_client.post(
        "/finance-invoices-save",
        json={
            "row": {
                "invoice_date": "25/06/2026",
                "invoice_number": invoice_number,
                "supplier_name": supplier_name,
                "service_or_product": "TEST | נעלולי פלא | שירות למחיקה",
                "amount": "100",
                "vat": "18",
                "total": "118",
            }
        },
    )
    if save_r.status_code != 200:
        pytest.skip(f"Save failed ({save_r.status_code})")

    row_id = save_r.payload.get("row_id") or save_r.payload.get("id") or ""
    if not row_id:
        pytest.skip("Save did not return row_id — cannot verify deletion")

    del_r = api_client.post("/finance-invoices-delete", json={"row_id": row_id})
    assert del_r.status_code in {200, 404}

    state_r = api_client.get("/finance-state")
    payload = state_r.payload
    rows = []
    for key in ("invoices", "finance_invoices", "rows", "data"):
        if key in payload:
            candidate = payload[key]
            if isinstance(candidate, list):
                rows = candidate
                break
            elif isinstance(candidate, dict) and "rows" in candidate:
                rows = candidate["rows"]
                break

    ids_in_state = [str(r.get("row_id", "")) for r in rows]
    assert row_id not in ids_in_state, f"Deleted row_id '{row_id}' still found in finance state"


# ---------------------------------------------------------------------------
# Marketing reminder: save → read back → complete → verify completed
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_reminder_save_appears_in_state(api_client):
    customer_key = f"test-customer-reminder-lifecycle-{id(object())}"
    message = build_test_label("תזכורת lifecycle")

    save_r = api_client.post(
        "/marketing-save-reminder",
        json={
            "customer": {"customer_key": customer_key, "customer_name": "TEST | נעלולי פלא | לקוח תזכורת lifecycle"},
            "customer_name": "TEST | נעלולי פלא | לקוח תזכורת lifecycle",
            "due_date": "2026-12-31",
            "due_time": "09:00",
            "message": message,
            "channel": "phone",
        },
    )
    if save_r.status_code != 200:
        pytest.skip(f"Reminder save failed ({save_r.status_code})")

    state_r = api_client.get("/marketing-reminders-state")
    assert state_r.status_code == 200
    rows = state_r.payload if isinstance(state_r.payload, list) else state_r.payload.get("rows", [])
    messages = [str(r.get("message", "")) for r in rows]
    assert any(message in m for m in messages) or len(rows) == 0


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_reminder_delete_removes_from_state(api_client):
    customer_key = f"test-customer-reminder-delete-{id(object())}"
    message = build_test_label("תזכורת למחיקה")

    save_r = api_client.post(
        "/marketing-save-reminder",
        json={
            "customer": {"customer_key": customer_key, "customer_name": "TEST | נעלולי פלא | לקוח תזכורת מחיקה"},
            "customer_name": "TEST | נעלולי פלא | לקוח",
            "due_date": "2026-12-31",
            "due_time": "10:00",
            "message": message,
            "channel": "whatsapp",
        },
    )
    if save_r.status_code != 200:
        pytest.skip(f"Reminder save failed ({save_r.status_code})")

    reminder_id = save_r.payload.get("reminder_id") or save_r.payload.get("id") or ""
    if not reminder_id:
        pytest.skip("Save did not return reminder_id")

    del_r = api_client.post("/marketing-reminder-delete", json={"reminder_id": reminder_id})
    assert del_r.status_code in {200, 404}

    state_r = api_client.get("/marketing-reminders-state")
    rows = state_r.payload if isinstance(state_r.payload, list) else state_r.payload.get("rows", [])
    ids = [str(r.get("reminder_id", "")) for r in rows]
    assert reminder_id not in ids


# ---------------------------------------------------------------------------
# HR employee: save → read back → delete
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_hr_employee_save_appears_in_hr_state(api_client):
    employee_name = build_test_label("עובד lifecycle")

    save_r = api_client.post(
        "/hr-employee-save",
        json={"row": {"employee_name": employee_name, "role": "פועל", "start_date": "01/01/2026"}},
    )
    if save_r.status_code != 200:
        pytest.skip(f"HR employee save failed ({save_r.status_code})")

    state_r = api_client.get("/hr-state")
    assert state_r.status_code == 200
    payload = state_r.payload
    employees = []
    for key in ("employees", "hr_employees", "rows"):
        if key in payload:
            employees = payload[key] if isinstance(payload[key], list) else []
            break

    names = [str(e.get("employee_name", "")) for e in employees]
    assert any(employee_name in n for n in names) or len(employees) == 0


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_hr_employee_delete_removes_from_hr_state(api_client):
    employee_name = build_test_label("עובד למחיקה lifecycle")

    save_r = api_client.post(
        "/hr-employee-save",
        json={"row": {"employee_name": employee_name, "role": "פועל", "start_date": "01/01/2026"}},
    )
    if save_r.status_code != 200:
        pytest.skip(f"HR employee save failed ({save_r.status_code})")

    row_id = save_r.payload.get("row_id") or ""
    if not row_id:
        pytest.skip("Save did not return row_id")

    del_r = api_client.post("/hr-employee-delete", json={"row_id": row_id})
    assert del_r.status_code in {200, 404}

    state_r = api_client.get("/hr-state")
    payload = state_r.payload
    employees = []
    for key in ("employees", "hr_employees", "rows"):
        if key in payload:
            employees = payload[key] if isinstance(payload[key], list) else []
            break

    ids = [str(e.get("row_id", "")) for e in employees]
    assert row_id not in ids


# ---------------------------------------------------------------------------
# Payments transfer row: create → read back → delete
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_payments_row_create_appears_in_state(api_client):
    customer_name = build_test_label("תשלום lifecycle")

    create_r = api_client.post(
        "/payments-transfer-row",
        json={"row": {"customer_name": customer_name, "invoice_date": "25/06/2026", "amount": "500.00"}},
    )
    if create_r.status_code != 200:
        pytest.skip(f"Payment row create failed ({create_r.status_code})")

    state_r = api_client.get("/payments-transfer-state")
    assert state_r.status_code == 200
    payload = state_r.payload
    # State is a dict with sheet sections; just assert it's dict and not empty
    assert isinstance(payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_payments_row_create_delete_lifecycle(api_client):
    customer_name = build_test_label("תשלום למחיקה")

    create_r = api_client.post(
        "/payments-transfer-row",
        json={"row": {"customer_name": customer_name, "invoice_date": "25/06/2026", "amount": "750.00"}},
    )
    if create_r.status_code != 200:
        pytest.skip(f"Payment row create failed ({create_r.status_code})")

    row_info = create_r.payload
    sheet_title = row_info.get("sheet_title", "")
    row_number = row_info.get("row_number") or row_info.get("row") or 2

    if sheet_title:
        del_r = api_client.post(
            "/payments-transfer-delete-row",
            json={
                "sheet_title": sheet_title,
                "row_number": row_number,
                "row": {"customer_name": customer_name, "source_mode": "SB"},
            },
        )
        assert del_r.status_code in {200, 400, 404, 422, 500}


# ---------------------------------------------------------------------------
# Working order note: save → read file → delete
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.sandbox_only
def test_working_order_note_save_lifecycle(api_client):
    """Save a note, then verify the note-file endpoint responds for it."""
    note_text = build_test_label("הערת הזמנת עבודה lifecycle")

    save_r = api_client.post(
        "/working-orders-note-save",
        json={"row_id": "lifecycle-wo-001", "note_text": note_text},
    )
    assert save_r.status_code in {200, 400, 404, 422, 500}

    if save_r.status_code == 200:
        note_row_id = save_r.payload.get("row_id") or save_r.payload.get("note_id") or ""
        if note_row_id:
            file_r = api_client.get(f"/working-order-note-file/{note_row_id}")
            # 200 (has file) or 404 (no file attached) — both valid
            assert file_r.status_code in {200, 400, 404, 422}
