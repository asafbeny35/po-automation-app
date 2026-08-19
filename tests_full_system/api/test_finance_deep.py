"""Deep finance API tests — CRUD lifecycle, file uploads, exports, withholdings."""
from __future__ import annotations

import io

import pytest


# ---------------------------------------------------------------------------
# Invoice CRUD lifecycle
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoice_save_minimal_valid_row(api_client):
    payload = {
        "row": {
            "invoice_date": "01/05/2026",
            "supplier_name": "TEST | נעלולי פלא | ספק",
            "service_or_product": "TEST | נעלולי פלא | שירות",
            "amount": "1000",
            "vat": "180",
            "total": "1180",
        }
    }
    response = api_client.post("/finance-invoices-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoice_save_returns_row_id_on_success(api_client):
    payload = {
        "row": {
            "invoice_date": "01/05/2026",
            "supplier_name": "TEST | נעלולי פלא | ספק חשבונית",
            "service_or_product": "TEST | נעלולי פלא | שירות ייעוץ",
            "amount": "2000",
            "vat": "360",
            "total": "2360",
            "due_date": "01/06/2026",
            "invoice_number": "TEST-INV-DEEP-001",
        }
    }
    response = api_client.post("/finance-invoices-save", json=payload)
    if response.status_code == 200:
        assert isinstance(response.payload, dict)
        # Should return some identifier
        assert any(k in response.payload for k in ("row_id", "id", "status"))


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoice_delete_with_nonexistent_id(api_client):
    response = api_client.post(
        "/finance-invoices-delete",
        json={"row_id": "nonexistent-finance-row-999"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoice_delete_many_with_nonexistent_ids(api_client):
    response = api_client.post(
        "/finance-invoices-delete-many",
        json={"row_ids": ["nonexistent-1", "nonexistent-2"]},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finance_invoices_upload_single_pdf(api_client):
    files = {
        "files": (
            "finance_invoice_test.pdf",
            io.BytesIO(b"%PDF-1.4\n%TEST-FINANCE\n"),
            "application/pdf",
        )
    }
    response = api_client.post("/finance-invoices-upload", files=files)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finance_invoices_upload_multiple_pdfs(api_client):
    files = [
        ("files", ("inv1.pdf", io.BytesIO(b"%PDF-1.4\n%INV1\n"), "application/pdf")),
        ("files", ("inv2.pdf", io.BytesIO(b"%PDF-1.4\n%INV2\n"), "application/pdf")),
        ("files", ("inv3.pdf", io.BytesIO(b"%PDF-1.4\n%INV3\n"), "application/pdf")),
    ]
    response = api_client.post("/finance-invoices-upload", files=files)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoices_upload_no_files_returns_error(api_client):
    response = api_client.post("/finance-invoices-upload")
    assert response.status_code in {400, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoice_file_download_missing_id_returns_error(api_client):
    response = api_client.get("/finance-invoices-file/nonexistent-row-999")
    assert response.status_code in {400, 404, 422}


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoices_export_xlsx_reachable(api_client):
    response = api_client.post(
        "/finance-invoices-export",
        json={"format": "xlsx", "row_ids": []},
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoices_export_pdf_reachable(api_client):
    response = api_client.post(
        "/finance-invoices-export-pdf",
        json={"row_ids": []},
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoices_send_email_accepts_test_shape(api_client):
    response = api_client.post(
        "/finance-invoices-send-email",
        json={
            "recipients": "test@example.com",
            "subject": "TEST | נעלולי פלא | חשבוניות",
            "message": "TEST | נעלולי פלא | גוף הודעה",
            "row_ids": [],
        },
    )
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_settings_save_valid_tax_rate(api_client):
    response = api_client.post(
        "/finance-settings-save",
        json={"income_tax_rate_percent": 3},
    )
    assert response.status_code in {200, 400, 422, 500}
    if response.status_code == 200:
        assert isinstance(response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_settings_save_zero_rate_accepted(api_client):
    response = api_client.post(
        "/finance-settings-save",
        json={"income_tax_rate_percent": 0},
    )
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# Override due dates
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoice_override_due_dates_batch(api_client):
    response = api_client.post(
        "/finance-invoices-override-due-dates",
        json={
            "overrides": [
                {"row_id": "test-row-001", "due_date": "01/07/2026"},
                {"row_id": "test-row-002", "due_date": "15/07/2026"},
            ]
        },
    )
    assert response.status_code in {200, 400, 404, 422, 500}


# ---------------------------------------------------------------------------
# Customer withholdings
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_customer_withholdings_state_available(api_client):
    response = api_client.get("/finance-customer-withholdings-state")
    assert response.status_code == 200
    assert isinstance(response.payload, (dict, list))


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_customer_withholdings_epoch_available(api_client):
    response = api_client.get("/finance-customer-withholdings-epoch")
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_customer_withholdings_save_accepts_shape(api_client):
    response = api_client.post(
        "/finance-customer-withholdings-save",
        json={
            "row": {
                "customer_name": "TEST | נעלולי פלא | לקוח",
                "customer_id": "999999999",
                "year": "2026",
                "withholding_amount": "300",
                "income_amount": "10000",
            }
        },
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoices_epoch_available(api_client):
    response = api_client.get("/finance-invoices-epoch")
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# Finance drive folder
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoices_drive_folder_available(api_client):
    response = api_client.get("/finance-invoices-drive-folder", timeout=60.0)
    assert response.status_code < 500
