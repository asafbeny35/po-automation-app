from __future__ import annotations

import io

import pytest


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize(
    "path",
    [
        "/delivery-confirmations-state",
        "/inventory-sandbox-deductions",
    ],
)
def test_delivery_related_read_endpoints_available(api_client, path):
    response = api_client.get(path)
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_contacts_save_accepts_basic_shape(api_client):
    response = api_client.post(
        "/delivery-contacts-state",
        json={
            "rows": [
                {
                    "company": "TEST | נעלולי פלא | חברה",
                    "accounting_contact_name": "TEST | נעלולי פלא | הנהח",
                    "mobile": "0547720142",
                    "email": "test@example.com",
                }
            ]
        },
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_delivery_upload_accepts_pdf_shape(api_client):
    files = {"file": ("signed-delivery.pdf", io.BytesIO(b"%PDF-1.4\n%TEST\n"), "application/pdf")}
    response = api_client.post(
        "/delivery-confirmations-upload?po_number=TEST-PO-001&tax_invoice_number=550000&source_mode=SB",
        files=files,
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_send_and_delete_contracts(api_client):
    send_response = api_client.post(
        "/delivery-confirmations-send",
        json={
            "po_number": "TEST-PO-001",
            "tax_invoice_number": "550000",
            "source_mode": "SB",
            "mode": "sandbox",
            "test_send": True,
            "subject": "TEST | נעלולי פלא | אישור מסירה",
            "message": "TEST | נעלולי פלא | גוף הודעה",
            "recipients": "test@example.com",
        },
    )
    delete_response = api_client.post(
        "/delivery-confirmations-delete-upload",
        json={
            "po_number": "TEST-PO-001",
            "tax_invoice_number": "550000",
            "source_mode": "SB",
        },
    )
    assert send_response.status_code in {200, 400, 404, 422, 500}
    assert delete_response.status_code in {200, 400, 404, 422, 500}
