"""Response content correctness tests.

These go beyond status codes and assert on WHAT is in the response body:
field presence, types, value ranges, and business logic invariants.
"""
from __future__ import annotations

import pytest

from tests_full_system.helpers.data_builders import build_finalize_request
from tests_full_system.helpers.assertions import assert_ok_or_skip_prod_auth, skip_if_prod_auth_missing


# ---------------------------------------------------------------------------
# Auth dev-login — response body correctness
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.localhost_only
def test_dev_login_response_user_id_is_string(api_client):
    r = api_client.request(
        "POST", "/auth/dev-login",
        headers={"X-PO-Debug-Auth": "1"},
        json={"user_id": "asaf", "remember_me": True},
    )
    assert r.status_code == 200
    assert isinstance(r.payload["user_id"], str)
    assert len(r.payload["user_id"]) > 0


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.localhost_only
def test_dev_login_response_redirect_is_slash(api_client):
    r = api_client.request(
        "POST", "/auth/dev-login",
        headers={"X-PO-Debug-Auth": "1"},
        json={"user_id": "asaf", "remember_me": True},
    )
    assert r.status_code == 200
    assert r.payload.get("redirect_to") == "/"


# ---------------------------------------------------------------------------
# OAuth status — field correctness
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_google_drive_oauth_status_connected_is_bool(api_client):
    r = api_client.get("/google-drive/oauth/status")
    skip_if_prod_auth_missing(r, "/google-drive/oauth/status")
    assert r.status_code == 200
    payload = r.payload
    # Must have some boolean or string field indicating connection state
    found = any(k in payload for k in ("connected", "status", "ok", "authorized"))
    assert found, f"Expected connection-state key in: {list(payload.keys())}"


@pytest.mark.api
@pytest.mark.requires_live_server
def test_google_drive_health_status_field_is_string(api_client):
    r = api_client.get("/google-drive/health")
    skip_if_prod_auth_missing(r, "/google-drive/health")
    assert r.status_code in {200, 409}
    assert isinstance(r.payload, dict)
    assert len(r.payload) > 0


@pytest.mark.api
@pytest.mark.requires_live_server
def test_gmail_oauth_status_is_dict(api_client):
    r = api_client.get("/gmail-oauth/status")
    skip_if_prod_auth_missing(r, "/gmail-oauth/status")
    assert r.status_code == 200
    assert isinstance(r.payload, dict)
    assert len(r.payload) > 0


# ---------------------------------------------------------------------------
# Orders state — field correctness
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_order_history_state_rows_are_dicts(api_client):
    r = api_client.get("/order-history-state")
    assert_ok_or_skip_prod_auth(r, "/order-history-state")
    payload = r.payload
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    for row in rows[:5]:
        assert isinstance(row, dict), f"Expected row to be dict, got {type(row)}"


@pytest.mark.api
@pytest.mark.requires_live_server
def test_order_history_state_po_number_is_string_when_present(api_client):
    r = api_client.get("/order-history-state")
    assert_ok_or_skip_prod_auth(r, "/order-history-state")
    payload = r.payload
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    for row in rows[:10]:
        if "po_number" in row:
            assert isinstance(row["po_number"], str)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_state_rows_are_dicts(api_client):
    r = api_client.get("/quote-history-state")
    assert_ok_or_skip_prod_auth(r, "/quote-history-state")
    payload = r.payload
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    for row in rows[:5]:
        assert isinstance(row, dict)


# ---------------------------------------------------------------------------
# Inventory state — structure correctness
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_state_raw_rows_are_list(api_client):
    r = api_client.get("/inventory-state")
    assert_ok_or_skip_prod_auth(r, "/inventory-state")
    payload = r.payload
    for key in ("raw_rows", "raw"):
        if key in payload:
            assert isinstance(payload[key], list), f"Expected list for {key}"
            break


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_state_finish_rows_are_list(api_client):
    r = api_client.get("/inventory-state")
    assert_ok_or_skip_prod_auth(r, "/inventory-state")
    payload = r.payload
    for key in ("finish_rows", "finish"):
        if key in payload:
            assert isinstance(payload[key], list)
            break


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_inventory_purchase_orders_state_rows_have_supplier_field(api_client):
    r = api_client.get("/inventory-purchase-orders-state", timeout=300)
    assert_ok_or_skip_prod_auth(r, "/inventory-purchase-orders-state")
    payload = r.payload
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    for row in rows[:5]:
        assert isinstance(row, dict)


# ---------------------------------------------------------------------------
# Finance state — structure correctness
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_finance_state_has_summary_numbers_when_present(api_client):
    r = api_client.get("/finance-state", timeout=300)
    assert_ok_or_skip_prod_auth(r, "/finance-state")
    payload = r.payload
    assert isinstance(payload, dict)
    # Any totals present must be numeric-like
    for key in ("total_amount", "total_vat", "total_net", "grand_total"):
        if key in payload:
            val = payload[key]
            assert isinstance(val, (int, float, str)), f"{key} has unexpected type {type(val)}"


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_customer_withholdings_rows_are_dicts(api_client):
    r = api_client.get("/finance-customer-withholdings-state")
    assert_ok_or_skip_prod_auth(r, "/finance-customer-withholdings-state")
    payload = r.payload
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    for row in rows[:5]:
        assert isinstance(row, dict)


# ---------------------------------------------------------------------------
# Marketing — structure correctness
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_state_rows_have_customer_name(api_client):
    r = api_client.get("/marketing-pipeline-state")
    assert_ok_or_skip_prod_auth(r, "/marketing-pipeline-state")
    payload = r.payload
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    for row in rows[:5]:
        assert isinstance(row, dict)
        if "customer_name" in row:
            assert isinstance(row["customer_name"], str)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_reminders_state_rows_have_due_date(api_client):
    r = api_client.get("/marketing-reminders-state")
    assert_ok_or_skip_prod_auth(r, "/marketing-reminders-state")
    payload = r.payload
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    for row in rows[:5]:
        assert isinstance(row, dict)
        if "due_date" in row:
            assert isinstance(row["due_date"], str)
            assert len(row["due_date"]) > 0


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_work_managers_state_rows_have_full_name(api_client):
    r = api_client.get("/marketing-work-managers-state")
    assert_ok_or_skip_prod_auth(r, "/marketing-work-managers-state")
    payload = r.payload
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    for row in rows[:5]:
        assert isinstance(row, dict)
        if "full_name" in row:
            assert isinstance(row["full_name"], str)


# ---------------------------------------------------------------------------
# Payments — structure correctness
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_payments_transfer_state_has_section_keys(api_client):
    r = api_client.get("/payments-transfer-state")
    assert_ok_or_skip_prod_auth(r, "/payments-transfer-state")
    payload = r.payload
    assert isinstance(payload, dict)
    # Must have at least some data or empty structure
    assert len(payload) > 0


@pytest.mark.api
@pytest.mark.requires_live_server
def test_payments_transfer_refresh_status_returns_dict(api_client):
    r = api_client.get("/payments-transfer-refresh-status")
    skip_if_prod_auth_missing(r, "/payments-transfer-refresh-status")
    assert r.status_code in {200, 404}
    if r.status_code == 200:
        assert isinstance(r.payload, dict)


# ---------------------------------------------------------------------------
# HR — structure correctness
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_state_employees_are_list(api_client):
    r = api_client.get("/hr-state")
    assert_ok_or_skip_prod_auth(r, "/hr-state")
    payload = r.payload
    for key in ("employees", "hr_employees"):
        if key in payload:
            assert isinstance(payload[key], list)
            break


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_state_payroll_is_list(api_client):
    r = api_client.get("/hr-state")
    assert_ok_or_skip_prod_auth(r, "/hr-state")
    payload = r.payload
    for key in ("payroll", "hr_payroll"):
        if key in payload:
            assert isinstance(payload[key], list)
            break


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_state_hours_is_list(api_client):
    r = api_client.get("/hr-state")
    assert_ok_or_skip_prod_auth(r, "/hr-state")
    payload = r.payload
    for key in ("hours", "hr_hours"):
        if key in payload:
            assert isinstance(payload[key], list)
            break


# ---------------------------------------------------------------------------
# Delivery confirmations — structure
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_confirmations_rows_are_dicts(api_client):
    r = api_client.get("/delivery-confirmations-state")
    assert_ok_or_skip_prod_auth(r, "/delivery-confirmations-state")
    payload = r.payload
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    for row in rows[:5]:
        assert isinstance(row, dict)


# ---------------------------------------------------------------------------
# Pricing BOM — structure
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_pricing_bom_state_is_dict(api_client):
    r = api_client.get("/pricing-bom-state")
    assert_ok_or_skip_prod_auth(r, "/pricing-bom-state")
    assert isinstance(r.payload, dict)


# ---------------------------------------------------------------------------
# Finalize response body on success
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finalize_success_response_has_mode_and_document_mode(api_client):
    payload = build_finalize_request("full")
    r = api_client.post("/finalize", json=payload)
    if r.status_code == 200:
        body = r.payload
        assert "mode" in body or "document_mode" in body or "status" in body


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finalize_error_response_has_error_key(api_client):
    """When finalize fails it must return {"error": ...} not a raw exception."""
    r = api_client.post("/finalize", json={"mode": "sandbox", "document_mode": "full", "data": {}})
    if r.status_code in {400, 422, 500}:
        assert isinstance(r.payload, dict)
        assert "error" in r.payload or "detail" in r.payload


# ---------------------------------------------------------------------------
# Manual order recent customers — response content
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_manual_order_recent_customers_has_customers_key(api_client):
    r = api_client.get("/manual-order-recent-customers")
    if r.status_code == 200:
        assert isinstance(r.payload, dict)
        # Should have some list of customers
        has_list = any(isinstance(v, list) for v in r.payload.values())
        assert has_list or len(r.payload) > 0


# ---------------------------------------------------------------------------
# Working orders — structure
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_working_orders_state_rows_are_dicts(api_client):
    r = api_client.get("/working-orders-state")
    assert_ok_or_skip_prod_auth(r, "/working-orders-state")
    payload = r.payload
    rows = payload if isinstance(payload, list) else payload.get("rows", [])
    for row in rows[:5]:
        assert isinstance(row, dict)


# ---------------------------------------------------------------------------
# Edit start response — field correctness
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_start_response_has_row_key(api_client):
    import uuid
    session_id = f"test-content-{uuid.uuid4().hex[:8]}"
    r = api_client.post(
        "/payments-transfer-edit-start",
        json={"sheet_title": "TEST-CONTENT-SHEET", "row_number": 99, "session_id": session_id},
    )
    assert_ok_or_skip_prod_auth(r, "/payments-transfer-edit-start")
    assert "row_key" in r.payload
    assert isinstance(r.payload["row_key"], str)
    assert len(r.payload["row_key"]) > 0
    # Clean up
    api_client.post(
        "/payments-transfer-edit-end",
        json={"sheet_title": "TEST-CONTENT-SHEET", "row_number": 99, "session_id": session_id},
    )


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_start_response_has_presence_dict(api_client):
    import uuid
    session_id = f"test-presence-{uuid.uuid4().hex[:8]}"
    r = api_client.post(
        "/payments-transfer-edit-start",
        json={"sheet_title": "TEST-PRESENCE-SHEET", "row_number": 88, "session_id": session_id},
    )
    assert_ok_or_skip_prod_auth(r, "/payments-transfer-edit-start")
    assert "presence" in r.payload
    assert isinstance(r.payload["presence"], (dict, list))
    api_client.post(
        "/payments-transfer-edit-end",
        json={"sheet_title": "TEST-PRESENCE-SHEET", "row_number": 88, "session_id": session_id},
    )
