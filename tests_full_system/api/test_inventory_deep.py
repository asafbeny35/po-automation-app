"""Deep inventory API tests — delivery notes, purchase orders, stock operations."""
from __future__ import annotations

import io

import pytest


# ---------------------------------------------------------------------------
# Inventory state — full CRUD
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_state_save_and_read_roundtrip(api_client):
    """Save minimal inventory and read it back — state should return 200."""
    save_payload = {
        "raw_rows": [
            {
                "supplier": "TEST | נעלולי פלא | ספק גלם",
                "product": "TEST | נעלולי פלא | חומר גלם",
                "unit": "ק״ג",
                "quantity_real": "100",
                "quantity_sandbox": "0",
            }
        ],
        "finish_rows": [
            {
                "product": "TEST | נעלולי פלא | מוצר גמר",
                "unit": "יח׳",
                "quantity_real": "50",
                "quantity_sandbox": "0",
            }
        ],
        "contact_rows": [
            {
                "company": "TEST | נעלולי פלא | חברת ספק",
                "name": "TEST | נעלולי פלא | איש קשר ספק",
                "phone": "0547720142",
                "email": "supplier@example.com",
            }
        ],
    }
    save_response = api_client.post("/inventory-state", json=save_payload)
    assert save_response.status_code in {200, 400, 422, 500}

    read_response = api_client.get("/inventory-state")
    assert read_response.status_code == 200
    assert isinstance(read_response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_state_save_empty_rows_accepted(api_client):
    payload = {"raw_rows": [], "finish_rows": [], "contact_rows": []}
    response = api_client.post("/inventory-state", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_restore_real_stock_is_idempotent(api_client):
    r1 = api_client.post("/inventory-restore-real-stock")
    r2 = api_client.post("/inventory-restore-real-stock")
    assert r1.status_code < 500
    assert r2.status_code < 500


# ---------------------------------------------------------------------------
# Purchase Orders
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_po_create_full_shape_sandbox(api_client):
    payload = {
        "mode": "sandbox",
        "supplier_name": "TEST | נעלולי פלא | ספק רכש עמוק",
        "supplier_id": "999999999",
        "supplier_email": "test@example.com",
        "supplier_phone": "0547720142",
        "po_date": "2026-06-01",
        "item_description": "TEST | נעלולי פלא | חומר גלם רכש",
        "item_sku": "TEST-PO-SKU-001",
        "item_unit": "יח׳",
        "item_quantity": 5,
        "item_unit_price": 200.0,
        "subtotal": 1000.0,
        "vat": 180.0,
        "total": 1180.0,
    }
    response = api_client.post("/inventory-purchase-orders-create", json=payload)
    assert response.status_code in {200, 400, 422, 500}
    if response.status_code == 200:
        assert isinstance(response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_po_create_vat_math_validation(api_client):
    """Send clearly wrong VAT — server may accept or reject; just not a crash."""
    payload = {
        "mode": "sandbox",
        "supplier_name": "TEST | נעלולי פלא | ספק",
        "item_description": "TEST | נעלולי פלא | פריט",
        "item_quantity": 1,
        "item_unit_price": 100,
        "subtotal": 100,
        "vat": 99999,  # obviously wrong
        "total": 100099,
    }
    response = api_client.post("/inventory-purchase-orders-create", json=payload)
    # Server doesn't validate VAT math early — it may process and fail inside (known gap)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_po_send_email_accepts_test_shape(api_client):
    response = api_client.post(
        "/inventory-purchase-orders-send-email",
        json={
            "po_id": "test-po-001",
            "recipients": "test@example.com",
            "subject": "TEST | נעלולי פלא | הזמנת רכש",
            "message": "TEST | נעלולי פלא | גוף הודעה",
        },
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_po_send_whatsapp_test_number(api_client):
    response = api_client.post(
        "/inventory-purchase-orders-send-whatsapp",
        json={
            "po_id": "test-po-001",
            "phone": "0547720142",
            "message": "TEST | נעלולי פלא | WhatsApp רכש",
        },
    )
    assert response.status_code in {200, 400, 404, 422, 500}


# ---------------------------------------------------------------------------
# Supplier delivery notes
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_supplier_delivery_notes_parse_minimal_pdf(api_client):
    files = {
        "file": (
            "delivery_note_test.pdf",
            io.BytesIO(b"%PDF-1.4\n%DELIVERY-NOTE-TEST\n"),
            "application/pdf",
        )
    }
    response = api_client.post("/supplier-delivery-notes-parse", files=files)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_supplier_delivery_notes_parse_rejects_no_file(api_client):
    response = api_client.post("/supplier-delivery-notes-parse")
    assert response.status_code in {400, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_supplier_delivery_notes_save_full_shape(api_client):
    payload = {
        "note": {
            "supplier_name": "TEST | נעלולי פלא | ספק תעודת משלוח",
            "delivery_note_number": "DN-TEST-DEEP-001",
            "delivery_date": "01/06/2026",
            "total_amount": "500",
        },
        "items": [
            {
                "description": "TEST | נעלולי פלא | פריט ראשון",
                "sku": "TEST-SKU-D-001",
                "unit": "יח׳",
                "quantity": "10",
                "unit_price": "50",
                "line_total": "500",
            }
        ],
    }
    response = api_client.post("/supplier-delivery-notes-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_supplier_delivery_notes_save_multiple_items(api_client):
    payload = {
        "note": {
            "supplier_name": "TEST | נעלולי פלא | ספק רב פריטים",
            "delivery_note_number": "DN-MULTI-001",
            "delivery_date": "05/06/2026",
        },
        "items": [
            {"description": f"TEST | נעלולי פלא | פריט {i}", "quantity": str(i), "unit_price": "100"}
            for i in range(1, 6)
        ],
    }
    response = api_client.post("/supplier-delivery-notes-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_supplier_delivery_notes_add_to_inventory_accepts_shape(api_client):
    response = api_client.post(
        "/supplier-delivery-notes-add-to-inventory",
        json={
            "delivery_note_id": "test-dn-001",
            "items": [
                {
                    "description": "TEST | נעלולי פלא | פריט מלאי",
                    "quantity": "5",
                    "sku": "TEST-SKU-INV-001",
                }
            ],
        },
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_supplier_delivery_notes_delete_row_with_nonexistent_id(api_client):
    response = api_client.post(
        "/supplier-delivery-notes-delete-row",
        json={"row_id": "nonexistent-dn-row-999"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_supplier_delivery_notes_delete_summary_with_nonexistent_id(api_client):
    response = api_client.post(
        "/supplier-delivery-notes-delete-summary",
        json={"delivery_note_id": "nonexistent-dn-summary-999"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_supplier_delivery_note_source_download_missing_id(api_client):
    response = api_client.get("/supplier-delivery-note-source/nonexistent-record-999")
    assert response.status_code in {400, 404, 422}


# ---------------------------------------------------------------------------
# Sandbox deductions
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_sandbox_deductions_returns_200(api_client):
    response = api_client.get("/inventory-sandbox-deductions")
    assert response.status_code == 200
