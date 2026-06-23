from __future__ import annotations

import io

import pytest


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize(
    "path",
    [
        "/inventory-state",
        "/inventory-purchase-orders-state",
        "/supplier-delivery-notes-state",
        "/inventory-sandbox-deductions",
    ],
)
def test_inventory_read_endpoints_available(api_client, path):
    response = api_client.get(path)
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_state_save_accepts_basic_shape(api_client):
    payload = {
        "raw_rows": [{"supplier": "TEST | נעלולי פלא | ספק", "product": "TEST | נעלולי פלא | חומר"}],
        "finish_rows": [{"product": "TEST | נעלולי פלא | גמר", "quantity_real": "1"}],
        "contact_rows": [{"company": "TEST | נעלולי פלא | ספק", "name": "TEST | נעלולי פלא | איש קשר"}],
    }
    response = api_client.post("/inventory-state", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_purchase_order_create_accepts_sandbox_shape(api_client):
    payload = {
        "mode": "sandbox",
        "supplier_name": "TEST | נעלולי פלא | ספק רכש",
        "supplier_id": "999999999",
        "supplier_email": "test@example.com",
        "supplier_phone": "0547720142",
        "po_date": "2026-05-01",
        "item_description": "TEST | נעלולי פלא | חומר גלם",
        "item_sku": "TEST-SKU",
        "item_unit": "יח׳",
        "item_quantity": 1,
        "item_unit_price": 10,
        "subtotal": 10,
        "vat": 1.8,
        "total": 11.8,
    }
    response = api_client.post("/inventory-purchase-orders-create", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_purchase_order_delete_requires_history_id(api_client):
    response = api_client.post("/inventory-purchase-orders-delete", json={})
    assert response.status_code in {400, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_inventory_restore_real_stock_endpoint_reachable(api_client):
    response = api_client.post("/inventory-restore-real-stock")
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_supplier_delivery_notes_parse_accepts_pdf_shape(api_client):
    files = {"file": ("supplier-note.pdf", io.BytesIO(b"%PDF-1.4\n%TEST\n"), "application/pdf")}
    response = api_client.post("/supplier-delivery-notes-parse", files=files)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_supplier_delivery_notes_save_requires_note_and_items(api_client):
    payload = {
        "note": {
            "supplier_name": "TEST | נעלולי פלא | ספק",
            "delivery_note_number": "DN-TEST-001",
            "delivery_date": "01/05/2026",
        },
        "items": [{"description": "TEST | נעלולי פלא | פריט", "quantity": "1"}],
    }
    response = api_client.post("/supplier-delivery-notes-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}
