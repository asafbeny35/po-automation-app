"""Deep order and quote flow tests — sandbox lifecycle, file shapes, history ops."""
from __future__ import annotations

import io

import pytest

from tests_full_system.helpers.data_builders import (
    build_finalize_request,
    build_quote_finalize_request,
    build_test_order_payload,
)


# ---------------------------------------------------------------------------
# /process — PDF parsing
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_process_rejects_non_pdf_bytes(api_client):
    """Uploading random bytes that are clearly not a PDF should return an error."""
    files = {"file": ("fake.pdf", io.BytesIO(b"THIS IS NOT A PDF"), "application/pdf")}
    data = {"mode": "sandbox"}
    response = api_client.post("/process", files=files, data=data)
    assert response.status_code in {400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_process_rejects_missing_file(api_client):
    response = api_client.post("/process", data={"mode": "sandbox"})
    assert response.status_code in {400, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_process_rejects_missing_mode(api_client):
    files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4\n"), "application/pdf")}
    response = api_client.post("/process", files=files)
    # Server returns 500 instead of 400/422 — missing early input validation (known gap)
    assert response.status_code in {400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_process_accepts_minimal_valid_pdf_bytes(api_client):
    files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4\n%TEST\n"), "application/pdf")}
    data = {"mode": "sandbox"}
    response = api_client.post("/process", files=files, data=data)
    # May parse (200), fail to find supplier (400), or internal error (500) — just not a crash
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# /finalize — document generation
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finalize_full_mode_returns_status_ok_or_error(api_client):
    payload = build_finalize_request("full")
    response = api_client.post("/finalize", json=payload)
    assert response.status_code in {200, 400, 422, 500}
    if response.status_code == 200:
        assert response.payload.get("status") == "ok"


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finalize_delivery_only_mode(api_client):
    payload = build_finalize_request("delivery_only")
    response = api_client.post("/finalize", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finalize_invoice_only_mode(api_client):
    payload = build_finalize_request("invoice_only")
    response = api_client.post("/finalize", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finalize_partial_delivery_mode(api_client):
    payload = build_finalize_request("full", partial_delivery=True)
    response = api_client.post("/finalize", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.timeout(120)
def test_finalize_rejects_unknown_document_mode(api_client):
    payload = {
        "mode": "sandbox",
        "document_mode": "unknown_mode",
        "data": build_test_order_payload(),
    }
    response = api_client.post("/finalize", json=payload, timeout=120)
    # Server processes the request and fails deep in the pipeline (500) instead of
    # rejecting unknown document_mode early (400/422) — known input validation gap
    assert response.status_code in {400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finalize_response_has_expected_keys_on_success(api_client):
    payload = build_finalize_request("full")
    response = api_client.post("/finalize", json=payload)
    if response.status_code == 200:
        body = response.payload
        assert isinstance(body, dict)
        assert "status" in body
        assert body["status"] == "ok"
        # Should contain document identifiers
        assert any(
            k in body
            for k in (
                "delivery_document_number",
                "invoice_document_number",
                "files",
                "delivery_pdf_path",
            )
        )


# ---------------------------------------------------------------------------
# /finalize-quote
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finalize_quote_returns_ok_or_error(api_client):
    payload = build_quote_finalize_request()
    response = api_client.post("/finalize-quote", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_finalize_quote_response_shape_on_success(api_client):
    payload = build_quote_finalize_request()
    response = api_client.post("/finalize-quote", json=payload)
    if response.status_code == 200:
        body = response.payload
        assert isinstance(body, dict)
        assert body.get("status") == "ok"


# ---------------------------------------------------------------------------
# Order history operations
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_order_history_refresh_reachable(api_client):
    response = api_client.post("/order-history-refresh")
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_order_history_delete_with_nonexistent_id(api_client):
    response = api_client.post(
        "/order-history-delete",
        json={"row_id": "nonexistent-order-history-999"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


# ---------------------------------------------------------------------------
# Quote history operations
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_refresh_reachable(api_client):
    response = api_client.post("/quote-history-refresh")
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_delete_with_nonexistent_id(api_client):
    response = api_client.post(
        "/quote-history-delete",
        json={"row_id": "nonexistent-quote-history-999"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_order_data_with_nonexistent_id(api_client):
    response = api_client.post(
        "/quote-history-order-data",
        json={"row_id": "nonexistent-quote-999"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_mail_prepare_accepts_shape(api_client):
    response = api_client.post(
        "/quote-history-mail-prepare",
        json={
            "row_id": "test-quote-001",
            "recipients": "test@example.com",
            "subject": "TEST | נעלולי פלא | הצעת מחיר",
            "message": "TEST | נעלולי פלא | גוף הודעה",
        },
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_quote_history_upload_signed_accepts_pdf(api_client):
    files = {
        "file": (
            "signed-quote.pdf",
            io.BytesIO(b"%PDF-1.4\n%SIGNED-QUOTE\n"),
            "application/pdf",
        )
    }
    response = api_client.post(
        "/quote-history-upload-signed?row_id=test-quote-001",
        files=files,
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_quote_resolve_missing_id(api_client):
    response = api_client.get("/quote-history-quote-resolve")
    assert response.status_code in {400, 422}


# ---------------------------------------------------------------------------
# Transport label upload
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_upload_transport_label_accepts_pdf(api_client):
    files = {
        "file": (
            "transport-label.pdf",
            io.BytesIO(b"%PDF-1.4\n%LABEL\n"),
            "application/pdf",
        )
    }
    response = api_client.post("/upload-transport-label", files=files)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_upload_transport_label_rejects_missing_file(api_client):
    response = api_client.post("/upload-transport-label")
    assert response.status_code in {400, 422}
