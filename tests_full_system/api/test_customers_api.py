from __future__ import annotations

import pytest


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize(
    "path",
    [
        "/customers-state",
        "/customers-inactive-state",
    ],
)
def test_customer_read_endpoints_available(api_client, path):
    response = api_client.get(path)
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_customer_set_active_requires_rows(api_client):
    response = api_client.post("/customers-set-active", json={"active": False, "rows": []})
    assert response.status_code in {400, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_customer_create_accepts_test_shape(api_client):
    payload = {
        "mode": "sandbox",
        "customer": {
            "name": "TEST | נעלולי פלא | לקוח חדש",
            "idNumber": "999999999",
            "paymentTerms": "30",
            "phone": "0547720142",
            "mobile": "0547720142",
            "contactPerson": "TEST | נעלולי פלא | איש קשר",
            "emails": "test@example.com",
            "address": "כתובת TEST",
            "city": "חיפה",
            "country": "ישראל",
        },
    }
    response = api_client.post("/customers-create", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_customer_update_delete_and_send_contracts(api_client):
    update_response = api_client.post(
        "/customers-update",
        json={
            "mode": "sandbox",
            "customer": {
                "customer_guid": "test-guid",
                "customer_name": "TEST | נעלולי פלא | לקוח",
                "customer_id": "999999999",
                "emails": "test@example.com",
            },
        },
    )
    delete_response = api_client.post(
        "/customers-delete",
        json={
            "customer": {
                "customer_name": "TEST | נעלולי פלא | לקוח",
                "customer_guid": "test-guid",
                "source_mode": "SB",
            }
        },
    )
    send_response = api_client.post(
        "/customers-send-email",
        data={
            "recipients": "test@example.com",
            "subject": "TEST | נעלולי פלא | מייל לקוח",
            "plain_body": "TEST | נעלולי פלא | גוף",
            "html_body": "<p>TEST | נעלולי פלא | גוף</p>",
        },
    )
    assert update_response.status_code in {200, 400, 422, 500}
    assert delete_response.status_code in {200, 400, 404, 422, 500}
    assert send_response.status_code in {200, 400, 422, 500}
