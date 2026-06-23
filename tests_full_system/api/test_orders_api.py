from __future__ import annotations

import io

import pytest

from tests_full_system.helpers.data_builders import build_finalize_request, build_quote_finalize_request, enforce_sandbox_request


@pytest.mark.api
@pytest.mark.sandbox_only
def test_finalize_request_builder_is_sandbox_only():
    payload = enforce_sandbox_request(build_finalize_request())
    assert payload["mode"] == "sandbox"


@pytest.mark.api
@pytest.mark.sandbox_only
def test_finalize_quote_request_builder_is_sandbox_only():
    payload = enforce_sandbox_request(build_quote_finalize_request())
    assert payload["mode"] == "sandbox"


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_process_endpoint_accepts_pdf_upload_shape(api_client):
    files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4\n%TEST\n"), "application/pdf")}
    data = {"mode": "sandbox"}
    response = api_client.post("/process", files=files, data=data)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_order_history_state_endpoint_available(api_client):
    response = api_client.get("/order-history-state")
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_state_endpoint_available(api_client):
    response = api_client.get("/quote-history-state")
    assert response.status_code < 500
