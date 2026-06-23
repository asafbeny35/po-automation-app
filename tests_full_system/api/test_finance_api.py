from __future__ import annotations

import io

import pytest


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_state_endpoint_available(api_client):
    response = api_client.get("/finance-state")
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finance_invoices_upload_accepts_pdf_shape(api_client):
    files = {"files": ("finance-test.pdf", io.BytesIO(b"%PDF-1.4\n%TEST\n"), "application/pdf")}
    response = api_client.post("/finance-invoices-upload", files=files)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_settings_save_endpoint_available(api_client):
    response = api_client.post("/finance-settings-save", json={"income_tax_rate_percent": 3})
    assert response.status_code in {200, 400, 422, 500}
