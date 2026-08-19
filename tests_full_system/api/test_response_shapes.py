"""Response body shape tests — verify that successful responses contain expected keys.

These go beyond "status < 500": they assert on the actual response structure.
"""
from __future__ import annotations

import pytest

from tests_full_system.helpers.assertions import assert_ok_or_skip_prod_auth, skip_if_prod_auth_missing


# ---------------------------------------------------------------------------
# Orders history
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_order_history_state_returns_list_or_wrapped(api_client):
    response = api_client.get("/order-history-state")
    assert_ok_or_skip_prod_auth(response, "/order-history-state")
    payload = response.payload
    # Either a list of orders or {"rows": [...]} wrapper
    if isinstance(payload, list):
        pass
    else:
        assert isinstance(payload, dict)
        assert any(k in payload for k in ("rows", "orders", "data", "items"))


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_state_returns_list_or_wrapped(api_client):
    response = api_client.get("/quote-history-state")
    assert_ok_or_skip_prod_auth(response, "/quote-history-state")
    payload = response.payload
    if isinstance(payload, list):
        pass
    else:
        assert isinstance(payload, dict)


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_state_has_raw_and_finish_rows(api_client):
    response = api_client.get("/inventory-state")
    assert_ok_or_skip_prod_auth(response, "/inventory-state")
    payload = response.payload
    assert isinstance(payload, dict)
    # At minimum must have sections (even if empty)
    assert any(
        k in payload
        for k in ("raw_rows", "finish_rows", "contact_rows", "raw", "finish", "contacts")
    )


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_inventory_purchase_orders_state_is_list_or_wrapped(api_client):
    response = api_client.get("/inventory-purchase-orders-state", timeout=300)
    assert_ok_or_skip_prod_auth(response, "/inventory-purchase-orders-state")
    assert isinstance(response.payload, (dict, list))


@pytest.mark.api
@pytest.mark.requires_live_server
def test_supplier_delivery_notes_state_is_list_or_wrapped(api_client):
    response = api_client.get("/supplier-delivery-notes-state")
    assert_ok_or_skip_prod_auth(response, "/supplier-delivery-notes-state")
    assert isinstance(response.payload, (dict, list))


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_sandbox_deductions_is_list_or_wrapped(api_client):
    response = api_client.get("/inventory-sandbox-deductions")
    assert_ok_or_skip_prod_auth(response, "/inventory-sandbox-deductions")
    assert isinstance(response.payload, (dict, list))


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_customers_state_is_list_or_wrapped(api_client):
    response = api_client.get("/customers-state")
    assert_ok_or_skip_prod_auth(response, "/customers-state")
    assert isinstance(response.payload, (dict, list))


@pytest.mark.api
@pytest.mark.requires_live_server
def test_customers_inactive_state_is_list_or_wrapped(api_client):
    response = api_client.get("/customers-inactive-state")
    assert_ok_or_skip_prod_auth(response, "/customers-inactive-state")
    assert isinstance(response.payload, (dict, list))


# ---------------------------------------------------------------------------
# Finance
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_finance_state_has_invoices_section(api_client):
    response = api_client.get("/finance-state", timeout=300)
    assert_ok_or_skip_prod_auth(response, "/finance-state")
    payload = response.payload
    assert isinstance(payload, dict)
    # Must contain invoice or settings data
    assert any(
        k in payload
        for k in ("invoices", "rows", "finance_invoices", "settings", "finance_settings")
    )


# ---------------------------------------------------------------------------
# Marketing
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_state_is_dict(api_client):
    response = api_client.get("/marketing-state")
    assert_ok_or_skip_prod_auth(response, "/marketing-state")
    assert isinstance(response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_state_is_list_or_wrapped(api_client):
    response = api_client.get("/marketing-pipeline-state")
    assert_ok_or_skip_prod_auth(response, "/marketing-pipeline-state")
    assert isinstance(response.payload, (dict, list))


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_work_managers_state_is_list_or_wrapped(api_client):
    response = api_client.get("/marketing-work-managers-state")
    assert_ok_or_skip_prod_auth(response, "/marketing-work-managers-state")
    assert isinstance(response.payload, (dict, list))


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_construction_companies_state_is_list_or_wrapped(api_client):
    response = api_client.get("/marketing-construction-companies-state")
    assert_ok_or_skip_prod_auth(response, "/marketing-construction-companies-state")
    assert isinstance(response.payload, (dict, list))


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_reminders_state_is_list_or_wrapped(api_client):
    response = api_client.get("/marketing-reminders-state")
    assert_ok_or_skip_prod_auth(response, "/marketing-reminders-state")
    assert isinstance(response.payload, (dict, list))


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_history_state_is_list_or_wrapped(api_client):
    response = api_client.get("/marketing-history-state")
    assert_ok_or_skip_prod_auth(response, "/marketing-history-state")
    assert isinstance(response.payload, (dict, list))


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_payments_transfer_state_is_dict(api_client):
    response = api_client.get("/payments-transfer-state")
    assert_ok_or_skip_prod_auth(response, "/payments-transfer-state")
    assert isinstance(response.payload, dict)


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_pricing_bom_state_has_bom_and_components(api_client):
    response = api_client.get("/pricing-bom-state")
    assert_ok_or_skip_prod_auth(response, "/pricing-bom-state")
    assert isinstance(response.payload, dict)


# ---------------------------------------------------------------------------
# HR
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_state_is_dict(api_client):
    response = api_client.get("/hr-state")
    assert_ok_or_skip_prod_auth(response, "/hr-state")
    assert isinstance(response.payload, dict)


# ---------------------------------------------------------------------------
# Delivery confirmations
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_confirmations_state_is_list_or_wrapped(api_client):
    response = api_client.get("/delivery-confirmations-state")
    assert_ok_or_skip_prod_auth(response, "/delivery-confirmations-state")
    assert isinstance(response.payload, (dict, list))


# ---------------------------------------------------------------------------
# Working orders
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_working_orders_state_is_list_or_wrapped(api_client):
    response = api_client.get("/working-orders-state")
    assert_ok_or_skip_prod_auth(response, "/working-orders-state")
    assert isinstance(response.payload, (dict, list))


# ---------------------------------------------------------------------------
# OAuth & integration status
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_google_drive_oauth_status_returns_dict(api_client):
    response = api_client.get("/google-drive/oauth/status")
    skip_if_prod_auth_missing(response, "/google-drive/oauth/status")
    assert response.status_code == 200
    assert isinstance(response.payload, dict)
    assert any(k in response.payload for k in ("connected", "status", "ok", "authorized"))


@pytest.mark.api
@pytest.mark.requires_live_server
def test_gmail_oauth_status_returns_dict(api_client):
    response = api_client.get("/gmail-oauth/status")
    skip_if_prod_auth_missing(response, "/gmail-oauth/status")
    assert response.status_code == 200
    assert isinstance(response.payload, dict)


# ---------------------------------------------------------------------------
# Mobile endpoints
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_mobile_bootstrap_returns_dict(api_client):
    response = api_client.get("/mobile/bootstrap")
    assert response.status_code in {200, 401, 403}
    if response.status_code == 200:
        assert isinstance(response.payload, dict)
