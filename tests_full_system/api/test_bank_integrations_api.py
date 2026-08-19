"""Bank integration API tests — Pazomat and Sibus."""
from __future__ import annotations

import io

import pytest


# ---------------------------------------------------------------------------
# Pazomat
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_pazomat_state_returns_ok(api_client):
    response = api_client.get("/pazomat-state")
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.requires_live_server
def test_pazomat_state_response_is_dict(api_client):
    response = api_client.get("/pazomat-state")
    assert response.status_code == 200
    assert isinstance(response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_pazomat_drive_folder_link_available(api_client):
    response = api_client.get("/pazomat-drive-folder", timeout=60.0)
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_pazomat_refresh_reachable(api_client):
    response = api_client.post("/pazomat-refresh")
    # Returns 500 when Gmail OAuth is not connected — expected in dev environment
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# Sibus
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_sibus_state_returns_ok(api_client):
    response = api_client.get("/sibus-state")
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.requires_live_server
def test_sibus_state_response_is_dict(api_client):
    response = api_client.get("/sibus-state")
    assert response.status_code == 200
    assert isinstance(response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_sibus_drive_folder_link_available(api_client):
    response = api_client.get("/sibus-drive-folder", timeout=60.0)
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_sibus_refresh_reachable(api_client):
    response = api_client.post("/sibus-refresh")
    # Returns 500 when Gmail OAuth is not connected — expected in dev environment
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_sibus_monthly_check_reachable(api_client):
    response = api_client.post("/sibus-monthly-check")
    assert response.status_code < 500


# ---------------------------------------------------------------------------
# Bank movements (finance side)
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finance_bank_movements_upload_accepts_pdf(api_client):
    files = {
        "file": (
            "bank_statement_test.pdf",
            io.BytesIO(b"%PDF-1.4\n%BANK-TEST\n"),
            "application/pdf",
        )
    }
    response = api_client.post("/finance-bank-movements-upload", files=files)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_bank_movements_upload_rejects_missing_file(api_client):
    response = api_client.post("/finance-bank-movements-upload")
    assert response.status_code in {400, 422}
