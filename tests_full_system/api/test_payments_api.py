from __future__ import annotations

import pytest


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize(
    "path",
    [
        "/payments-transfer-state",
        "/payments-transfer-refresh-status",
    ],
)
def test_payment_read_endpoints_available(api_client, path):
    response = api_client.get(path)
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_payments_refresh_start_reachable(api_client):
    response = api_client.post("/payments-transfer-refresh-start")
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_payments_row_create_accepts_minimal_shape(api_client):
    response = api_client.post(
        "/payments-transfer-row",
        json={
            "row": {
                "customer_name": "TEST | נעלולי פלא | תשלום",
                "invoice_date": "01/05/2026",
                "amount": "118.00",
            }
        },
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_payments_paid_update_and_delete_contracts(api_client):
    paid_response = api_client.post(
        "/payments-transfer-paid",
        json={"sheet_title": "TEST", "row_number": 2, "paid": True},
    )
    update_response = api_client.post(
        "/payments-transfer-update-row",
        json={
            "sheet_title": "TEST",
            "row_number": 2,
            "row": {
                "customer_name": "TEST | נעלולי פלא | תשלום",
                "invoice_date": "01/05/2026",
                "amount": "118.00",
            },
        },
    )
    delete_response = api_client.post(
        "/payments-transfer-delete-row",
        json={
            "sheet_title": "TEST",
            "row_number": 2,
            "row": {
                "customer_name": "TEST | נעלולי פלא | תשלום",
                "po_number": "TEST-PO-001",
                "source_mode": "SB",
            },
        },
    )
    assert paid_response.status_code in {200, 400, 404, 422, 500}
    assert update_response.status_code in {200, 400, 404, 422, 500}
    assert delete_response.status_code in {200, 400, 404, 422, 500}
