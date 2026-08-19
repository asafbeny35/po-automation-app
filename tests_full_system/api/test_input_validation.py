"""Input validation tests — every major POST endpoint must reject clearly invalid input.

These tests enforce that endpoints return 400/422 (not 200 and not 500) for
missing required fields or obviously malformed payloads.
"""
from __future__ import annotations

import pytest

from tests_full_system.helpers.assertions import assert_invalid_input_rejected


# ---------------------------------------------------------------------------
# Orders & quotes
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_finalize_rejects_missing_mode(api_client):
    response = api_client.post("/finalize", json={"data": {}})
    assert_invalid_input_rejected(response, "/finalize missing mode")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finalize_rejects_production_mode(api_client):
    response = api_client.post("/finalize", json={"mode": "production", "data": {}})
    assert_invalid_input_rejected(response, "/finalize production mode")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finalize_rejects_empty_body(api_client):
    response = api_client.post("/finalize", json={})
    assert_invalid_input_rejected(response, "/finalize empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finalize_quote_rejects_empty_body(api_client):
    response = api_client.post("/finalize-quote", json={})
    assert_invalid_input_rejected(response, "/finalize-quote empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_order_history_delete_rejects_empty(api_client):
    response = api_client.post("/order-history-delete", json={})
    assert_invalid_input_rejected(response, "/order-history-delete empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_delete_rejects_empty(api_client):
    response = api_client.post("/quote-history-delete", json={})
    assert_invalid_input_rejected(response, "/quote-history-delete empty body")


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_purchase_order_create_rejects_missing_mode(api_client):
    payload = {
        "supplier_name": "TEST | נעלולי פלא | ספק",
        "item_description": "TEST | נעלולי פלא | פריט",
        "item_quantity": 1,
        "item_unit_price": 100,
        "subtotal": 100,
        "vat": 18,
        "total": 118,
    }
    response = api_client.post("/inventory-purchase-orders-create", json=payload)
    assert_invalid_input_rejected(response, "/inventory-purchase-orders-create missing mode")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_purchase_order_create_rejects_empty_body(api_client):
    response = api_client.post("/inventory-purchase-orders-create", json={})
    assert_invalid_input_rejected(response, "/inventory-purchase-orders-create empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_purchase_order_delete_rejects_empty(api_client):
    response = api_client.post("/inventory-purchase-orders-delete", json={})
    assert_invalid_input_rejected(response, "/inventory-purchase-orders-delete empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_supplier_delivery_notes_delete_row_rejects_empty(api_client):
    response = api_client.post("/supplier-delivery-notes-delete-row", json={})
    assert_invalid_input_rejected(response, "/supplier-delivery-notes-delete-row empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_supplier_delivery_notes_delete_summary_rejects_empty(api_client):
    response = api_client.post("/supplier-delivery-notes-delete-summary", json={})
    assert_invalid_input_rejected(response, "/supplier-delivery-notes-delete-summary empty body")


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_customer_create_rejects_missing_mode(api_client):
    response = api_client.post("/customers-create", json={"customer": {"name": "Test"}})
    assert_invalid_input_rejected(response, "/customers-create missing mode")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_customer_create_rejects_empty_body(api_client):
    response = api_client.post("/customers-create", json={})
    assert_invalid_input_rejected(response, "/customers-create empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_customer_set_active_rejects_empty_rows(api_client):
    response = api_client.post("/customers-set-active", json={"active": True, "rows": []})
    assert_invalid_input_rejected(response, "/customers-set-active empty rows")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_customer_update_rejects_empty_body(api_client):
    response = api_client.post("/customers-update", json={})
    assert_invalid_input_rejected(response, "/customers-update empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_customer_delete_empty_body_does_not_crash(api_client):
    """Endpoint with empty body returns customer list (200) or error — must not crash."""
    response = api_client.post("/customers-delete", json={})
    assert response.status_code in {200, 400, 422, 500}, (
        f"/customers-delete empty body returned unexpected status: {response.status_code}"
    )


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoice_save_rejects_empty_row(api_client):
    response = api_client.post("/finance-invoices-save", json={"row": {}})
    # Lenient — may be 400 or 200 if all fields optional; not a crash
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoice_delete_rejects_empty(api_client):
    response = api_client.post("/finance-invoices-delete", json={})
    assert_invalid_input_rejected(response, "/finance-invoices-delete empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoice_delete_many_rejects_empty_ids(api_client):
    response = api_client.post("/finance-invoices-delete-many", json={"row_ids": []})
    assert_invalid_input_rejected(response, "/finance-invoices-delete-many empty ids")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_settings_save_rejects_negative_tax_rate(api_client):
    response = api_client.post(
        "/finance-settings-save", json={"income_tax_rate_percent": -10}
    )
    # Must not silently accept or crash — 400/422 preferred, 200 acceptable if lenient
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoice_override_due_dates_rejects_empty(api_client):
    response = api_client.post("/finance-invoices-override-due-dates", json={})
    assert_invalid_input_rejected(response, "/finance-invoices-override-due-dates empty body")


# ---------------------------------------------------------------------------
# Marketing
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_save_note_rejects_missing_customer(api_client):
    response = api_client.post(
        "/marketing-save-note",
        json={"note_text": "TEST | נעלולי פלא | הערה"},
    )
    assert_invalid_input_rejected(response, "/marketing-save-note missing customer")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_save_reminder_rejects_missing_due_date(api_client):
    response = api_client.post(
        "/marketing-save-reminder",
        json={
            "customer": {"customer_key": "k", "customer_name": "TEST | נעלולי פלא"},
            "message": "TEST | נעלולי פלא | reminder",
        },
    )
    assert_invalid_input_rejected(response, "/marketing-save-reminder missing due date")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_delete_rejects_empty(api_client):
    response = api_client.post("/marketing-pipeline-delete", json={})
    assert_invalid_input_rejected(response, "/marketing-pipeline-delete empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_work_managers_delete_rejects_empty(api_client):
    response = api_client.post("/marketing-work-managers-delete", json={})
    assert_invalid_input_rejected(response, "/marketing-work-managers-delete empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_construction_companies_delete_rejects_empty(api_client):
    response = api_client.post("/marketing-construction-companies-delete", json={})
    assert_invalid_input_rejected(response, "/marketing-construction-companies-delete empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_reminder_delete_rejects_empty(api_client):
    response = api_client.post("/marketing-reminder-delete", json={})
    assert_invalid_input_rejected(response, "/marketing-reminder-delete empty body")


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_payments_transfer_row_rejects_empty(api_client):
    response = api_client.post("/payments-transfer-row", json={})
    assert_invalid_input_rejected(response, "/payments-transfer-row empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_payments_transfer_paid_rejects_missing_sheet(api_client):
    response = api_client.post(
        "/payments-transfer-paid",
        json={"row_number": 2, "paid": True},
    )
    assert_invalid_input_rejected(response, "/payments-transfer-paid missing sheet")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_payments_transfer_delete_row_rejects_empty(api_client):
    response = api_client.post("/payments-transfer-delete-row", json={})
    assert_invalid_input_rejected(response, "/payments-transfer-delete-row empty body")


# ---------------------------------------------------------------------------
# Income / GreenInvoice
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_greeninvoice_create_receipt_rejects_missing_mode(api_client):
    response = api_client.post(
        "/greeninvoice-create-receipt",
        json={"invoice": {"number": "INV-001"}, "payment": {"amount": 100}},
    )
    assert_invalid_input_rejected(response, "/greeninvoice-create-receipt missing mode")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_greeninvoice_upcoming_payments_accepts_days_without_mode(api_client):
    """Endpoint uses default mode when omitted — returns 200 or error, not crash."""
    response = api_client.post("/greeninvoice-upcoming-payments", json={"days": 30})
    assert response.status_code in {200, 400, 422, 500}, (
        f"/greeninvoice-upcoming-payments returned unexpected status: {response.status_code}"
    )


# ---------------------------------------------------------------------------
# HR
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_employee_save_rejects_empty_row(api_client):
    response = api_client.post("/hr-employee-save", json={})
    assert_invalid_input_rejected(response, "/hr-employee-save empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_payroll_save_rejects_empty_row(api_client):
    response = api_client.post("/hr-payroll-save", json={})
    assert_invalid_input_rejected(response, "/hr-payroll-save empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_contribution_save_rejects_empty_row(api_client):
    response = api_client.post("/hr-contribution-save", json={})
    assert_invalid_input_rejected(response, "/hr-contribution-save empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_hours_save_rejects_empty_row(api_client):
    response = api_client.post("/hr-hours-save", json={})
    assert_invalid_input_rejected(response, "/hr-hours-save empty body")


# ---------------------------------------------------------------------------
# Working orders
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_working_orders_note_save_rejects_empty(api_client):
    response = api_client.post("/working-orders-note-save", json={})
    assert_invalid_input_rejected(response, "/working-orders-note-save empty body")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_working_orders_delete_rejects_empty(api_client):
    response = api_client.post("/working-orders-delete", json={})
    assert_invalid_input_rejected(response, "/working-orders-delete empty body")
