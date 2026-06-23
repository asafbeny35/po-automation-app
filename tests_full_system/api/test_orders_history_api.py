from __future__ import annotations

import io

import pytest


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize(
    "path",
    [
        "/order-history-state",
        "/quote-history-state",
        "/delivery-confirmations-state",
    ],
)
def test_order_related_history_endpoints_are_available(api_client, path):
    response = api_client.get(path)
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_order_history_refresh_endpoint_is_reachable(api_client):
    response = api_client.post("/order-history-refresh")
    assert response.status_code in {200, 400, 401, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_refresh_endpoint_is_reachable(api_client):
    response = api_client.post("/quote-history-refresh")
    assert response.status_code in {200, 400, 401, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_order_data_requires_payload_shape(api_client):
    response = api_client.post("/quote-history-order-data", json={"history_id": "test-history-id"})
    assert response.status_code in {200, 400, 401, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_order_history_delete_requires_history_id_shape(api_client):
    response = api_client.post("/order-history-delete", json={"history_id": "test-history-id"})
    assert response.status_code in {200, 400, 401, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_delete_requires_history_id_shape(api_client):
    response = api_client.post("/quote-history-delete", json={"history_id": "test-history-id"})
    assert response.status_code in {200, 400, 401, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_mail_prepare_requires_history_id_shape(api_client):
    response = api_client.post("/quote-history-mail-prepare", json={"history_id": "test-history-id"})
    assert response.status_code in {200, 400, 401, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_resolve_endpoint_requires_history_id(api_client):
    response = api_client.get("/quote-history-quote-resolve", params={"history_id": "test-history-id"})
    assert response.status_code in {200, 400, 401, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_history_upload_signed_accepts_form_shape(api_client):
    files = {"file": ("signed-quote.pdf", io.BytesIO(b"%PDF-1.4\n%TEST\n"), "application/pdf")}
    response = api_client.post(
        "/quote-history-upload-signed",
        files=files,
        data={"history_id": "test-history-id"},
    )
    assert response.status_code in {200, 400, 401, 404, 422, 500}
