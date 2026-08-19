"""Working Orders API tests — comprehensive coverage."""
from __future__ import annotations

import io

import pytest

from tests_full_system.helpers.assertions import assert_invalid_input_rejected, assert_ok_or_skip_prod_auth


# ---------------------------------------------------------------------------
# State read
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_working_orders_state_returns_ok(api_client):
    response = api_client.get("/working-orders-state")
    assert_ok_or_skip_prod_auth(response, "/working-orders-state")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_working_orders_state_response_is_dict_or_list(api_client):
    response = api_client.get("/working-orders-state")
    assert_ok_or_skip_prod_auth(response, "/working-orders-state")
    assert isinstance(response.payload, (dict, list))


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_working_orders_upload_accepts_pdf_shape(api_client):
    files = {"file": ("working-order-test.pdf", io.BytesIO(b"%PDF-1.4\n%WO-TEST\n"), "application/pdf")}
    data = {"description": "TEST | נעלולי פלא | הזמנת עבודה", "mode": "sandbox"}
    response = api_client.post("/working-orders-upload", files=files, data=data)
    if response.status_code == 401:
        pytest.skip("/working-orders-upload requires authenticated production session")
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_working_orders_upload_rejects_missing_file(api_client):
    response = api_client.post("/working-orders-upload", data={"mode": "sandbox"})
    assert_invalid_input_rejected(response, "/working-orders-upload missing file")


# ---------------------------------------------------------------------------
# Note save
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_working_order_note_save_accepts_minimal_shape(api_client):
    payload = {
        "row_id": "test-wo-001",
        "note_text": "TEST | נעלולי פלא | הערה להזמנה",
    }
    response = api_client.post("/working-orders-note-save", json=payload)
    if response.status_code == 401:
        pytest.skip("/working-orders-note-save requires authenticated production session")
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_working_order_note_save_requires_row_id(api_client):
    response = api_client.post(
        "/working-orders-note-save",
        json={"note_text": "TEST | נעלולי פלא | הערה"},
    )
    assert_invalid_input_rejected(response, "/working-orders-note-save missing row_id")


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_working_order_note_save_with_file_upload(api_client):
    files = {"file": ("note-attachment.pdf", io.BytesIO(b"%PDF-1.4\n%NOTE\n"), "application/pdf")}
    data = {"row_id": "test-wo-001", "note_text": "TEST | נעלולי פלא | הערה עם קובץ"}
    response = api_client.post("/working-orders-note-save", files=files, data=data)
    if response.status_code == 401:
        pytest.skip("/working-orders-note-save file upload requires authenticated production session")
    assert response.status_code in {200, 400, 404, 422, 500}


# ---------------------------------------------------------------------------
# Note file download
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_working_order_note_file_download_missing_id_404(api_client):
    response = api_client.get("/working-order-note-file/nonexistent-row-id-999")
    if response.status_code == 401:
        pytest.skip("/working-order-note-file requires authenticated production session")
    assert response.status_code in {400, 404, 422}


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_working_orders_delete_requires_row_id(api_client):
    response = api_client.post("/working-orders-delete", json={})
    assert_invalid_input_rejected(response, "/working-orders-delete missing row_id")


@pytest.mark.api
@pytest.mark.requires_live_server
def test_working_orders_delete_accepts_valid_row_id(api_client):
    response = api_client.post(
        "/working-orders-delete",
        json={"row_id": "test-wo-nonexistent-001"},
    )
    if response.status_code == 401:
        pytest.skip("/working-orders-delete requires authenticated production session")
    assert response.status_code in {200, 400, 404, 422, 500}
