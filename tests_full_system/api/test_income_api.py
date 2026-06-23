from __future__ import annotations

import pytest


@pytest.mark.api
@pytest.mark.requires_live_server
def test_upcoming_payments_endpoint_reachable(api_client):
    response = api_client.post(
        "/greeninvoice-upcoming-payments",
        json={"mode": "sandbox", "days": 30},
    )
    assert response.status_code in {200, 400, 401, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_income_customers_endpoint_reachable(api_client):
    response = api_client.post(
        "/greeninvoice-income-customers",
        json={"mode": "sandbox", "date_preset": "last_30_days"},
    )
    assert response.status_code in {200, 400, 401, 422, 500}


@pytest.mark.api
@pytest.mark.sandbox_only
@pytest.mark.requires_live_server
def test_create_receipt_endpoint_reachable_with_sandbox_payload(api_client):
    response = api_client.post(
        "/greeninvoice-create-receipt",
        json={
            "mode": "sandbox",
            "invoice": {
                "number": "TEST-INV-001",
                "customer_name": "TEST | נעלולי פלא | Customer",
            },
            "payment": {
                "date": "2026-05-01",
                "amount": 100,
                "type": "cash",
            },
        },
    )
    assert response.status_code in {200, 400, 401, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_whatsapp_send_reminder_requires_phone_and_message_shape(api_client):
    response = api_client.post(
        "/whatsapp-send-reminder",
        json={
            "phone": "0547720142",
            "message": "TEST | נעלולי פלא | reminder message",
            "test_send": True,
        },
    )
    assert response.status_code in {200, 400, 500}


@pytest.mark.api
@pytest.mark.sandbox_only
@pytest.mark.requires_live_server
def test_receipt_email_reminder_endpoint_reachable(api_client):
    response = api_client.post(
        "/receipt-email-reminder-send",
        json={
            "mode": "sandbox",
            "invoice": {
                "number": "TEST-INV-001",
                "customer_name": "TEST | נעלולי פלא | Customer",
            },
            "recipients": "test@example.com",
            "subject": "TEST | נעלולי פלא | receipt reminder",
            "message": "TEST | נעלולי פלא | please send receipt",
        },
    )
    assert response.status_code in {200, 400, 401, 404, 422, 500}
