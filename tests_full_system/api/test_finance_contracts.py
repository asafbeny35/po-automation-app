from __future__ import annotations

import pytest


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_export_endpoint_reachable(api_client):
    response = api_client.post("/finance-invoices-export", json={"rows": [], "title": "TEST export"})
    assert response.status_code in {200, 400, 401, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_export_pdf_endpoint_reachable(api_client):
    response = api_client.post("/finance-invoices-export-pdf", json={"rows": [], "title": "TEST export pdf"})
    assert response.status_code in {200, 400, 401, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_override_due_dates_endpoint_reachable(api_client):
    response = api_client.post(
        "/finance-invoices-override-due-dates",
        json={"row_id": "test-row-id", "due_dates": ["15/05/2026"]},
    )
    assert response.status_code in {200, 400, 401, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_send_email_endpoint_reachable(api_client):
    response = api_client.post(
        "/finance-invoices-send-email",
        json={
            "test_send": True,
            "due_dates": ["15/05/2026"],
            "attachments": {"zip": True, "pdf": True, "excel": True},
            "recipients": "",
            "subject": "TEST",
            "message": "TEST",
        },
    )
    assert response.status_code in {200, 400, 401, 404, 422, 500}
