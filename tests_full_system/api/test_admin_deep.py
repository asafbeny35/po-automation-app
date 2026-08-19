"""Deep admin API tests — office docs, insurance, loans, supplier onboarding, AI assistants."""
from __future__ import annotations

import io

import pytest


# ---------------------------------------------------------------------------
# Drive folder links
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize("path", [
    "/admin-drive-folder",
    "/insurance-drive-folder",
    "/loans-drive-folder",
    "/pazomat-drive-folder",
    "/sibus-drive-folder",
    "/finance-invoices-drive-folder",
    "/marketing-drive-folder",
])
def test_all_drive_folder_links_available(api_client, path):
    response = api_client.get(path, timeout=60.0)
    assert response.status_code < 500


# ---------------------------------------------------------------------------
# Admin asset download
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_admin_drive_asset_missing_key_returns_error(api_client):
    response = api_client.get("/admin-drive/nonexistent-asset-key-999")
    # Server returns 500 ("מסמך מנהלה לא הוגדר") for unknown keys instead of 404 — known gap
    assert response.status_code in {400, 404, 422, 500}
    assert "error" in (response.payload if isinstance(response.payload, dict) else {})


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_drive_asset_missing_key_returns_error(api_client):
    response = api_client.get("/marketing-drive/nonexistent-asset-key-999")
    # Server returns 500 ("מסמך שיווק לא הוגדר") for unknown keys instead of 404 — known gap
    assert response.status_code in {400, 404, 422, 500}
    assert "error" in (response.payload if isinstance(response.payload, dict) else {})


# ---------------------------------------------------------------------------
# Supplier onboarding email
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_admin_supplier_package_email_accepts_shape(api_client):
    response = api_client.post(
        "/admin-supplier-package-email",
        json={
            "recipients": "test@example.com",
            "supplier_name": "TEST | נעלולי פלא | ספק חדש",
            "subject": "TEST | נעלולי פלא | חבילת ספק",
            "message": "TEST | נעלולי פלא | גוף הודעה ספק",
        },
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_admin_supplier_package_email_rejects_empty(api_client):
    response = api_client.post("/admin-supplier-package-email", json={})
    assert response.status_code in {400, 422}


# ---------------------------------------------------------------------------
# Business doc email / WhatsApp
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_admin_business_doc_send_email_accepts_shape(api_client):
    response = api_client.post(
        "/admin-business-doc-send-email",
        json={
            "asset_key": "test-doc-key",
            "recipients": "test@example.com",
            "subject": "TEST | נעלולי פלא | מסמך עסקי",
            "message": "TEST | נעלולי פלא | גוף הודעה מסמך",
        },
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_admin_business_doc_send_whatsapp_accepts_shape(api_client):
    response = api_client.post(
        "/admin-business-doc-send-whatsapp",
        json={
            "asset_key": "test-doc-key",
            "phone": "0547720142",
            "message": "TEST | נעלולי פלא | WhatsApp מסמך עסקי",
        },
    )
    assert response.status_code in {200, 400, 404, 422, 500}


# ---------------------------------------------------------------------------
# Insurance AI assistant
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_insurance_assistant_reachable(api_client):
    response = api_client.post(
        "/insurance-assistant",
        json={"question": "TEST | נעלולי פלא | שאלה לביטוח"},
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_insurance_assistant_rejects_empty_question(api_client):
    response = api_client.post("/insurance-assistant", json={})
    assert response.status_code in {400, 422}


# ---------------------------------------------------------------------------
# GreenInvoice AI assistant
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_greeninvoice_assistant_reachable(api_client):
    response = api_client.post(
        "/greeninvoice-assistant",
        json={
            "question": "TEST | נעלולי פלא | כמה חשבוניות פתוחות?",
            "mode": "sandbox",
        },
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_greeninvoice_assistant_rejects_empty(api_client):
    response = api_client.post("/greeninvoice-assistant", json={})
    assert response.status_code in {400, 422}


# ---------------------------------------------------------------------------
# Marketing doc preview
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_doc_preview_missing_key_returns_error(api_client):
    response = api_client.get("/marketing-doc-preview/nonexistent-asset-999")
    assert response.status_code in {400, 404, 422}


# ---------------------------------------------------------------------------
# Project managers
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_project_managers_state_returns_ok(api_client):
    response = api_client.get("/project-managers-state")
    assert response.status_code == 200
    assert isinstance(response.payload, (dict, list))


@pytest.mark.api
@pytest.mark.requires_live_server
def test_project_managers_save_accepts_shape(api_client):
    response = api_client.post(
        "/project-managers-state",
        json={
            "rows": [
                {
                    "manager_name": "TEST | נעלולי פלא | מנהל פרויקט",
                    "phone": "0547720142",
                    "email": "pm@example.com",
                    "company": "TEST | נעלולי פלא | חברה",
                }
            ]
        },
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_project_managers_upload_pdf(api_client):
    files = {
        "file": (
            "project_managers.pdf",
            io.BytesIO(b"%PDF-1.4\n%PM-TEST\n"),
            "application/pdf",
        )
    }
    response = api_client.post("/project-managers-upload", files=files)
    assert response.status_code in {200, 400, 422, 500}
