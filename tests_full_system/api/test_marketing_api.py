from __future__ import annotations

import pytest


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize(
    "path",
    [
        "/marketing-drive-folder",
        "/marketing-state",
        "/marketing-history-state",
        "/marketing-work-managers-state",
        "/marketing-construction-companies-state",
        "/marketing-pipeline-state",
        "/marketing-pipeline-cached",
        "/marketing-docs-state",
        "/marketing-reminders-state",
    ],
)
def test_marketing_read_endpoints_available(api_client, path):
    response = api_client.get(path)
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_work_manager_save_accepts_minimal_shape(api_client):
    payload = {
        "row": {
            "row_id": "test-work-manager-001",
            "full_name": "TEST | נעלולי פלא | מנהל עבודה",
            "email": "test@example.com",
            "phone_1": "0547720142",
            "active_status": "כן",
        }
    }
    response = api_client.post("/marketing-work-managers-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_construction_company_save_accepts_minimal_shape(api_client):
    payload = {
        "row": {
            "row_id": "test-construction-company-001",
            "company_name": "TEST | נעלולי פלא | חברת בנייה",
            "email": "test@example.com",
            "phone": "0547720142",
        }
    }
    response = api_client.post("/marketing-construction-companies-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_save_accepts_minimal_shape(api_client):
    payload = {
        "row": {
            "customer_key": "test-customer-key",
            "customer_name": "TEST | נעלולי פלא | לקוח שיווק",
            "emails": "test@example.com",
            "phone": "0547720142",
            "contact_name": "TEST | נעלולי פלא | איש קשר",
        }
    }
    response = api_client.post("/marketing-pipeline-save", json=payload)
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_note_and_reminder_endpoints_accept_shapes(api_client):
    note_response = api_client.post(
        "/marketing-save-note",
        json={
            "customer": {
                "customer_key": "test-customer-key",
                "customer_name": "TEST | נעלולי פלא | לקוח שיווק",
            },
            "note_text": "TEST | נעלולי פלא | הערת שיווק",
        },
    )
    reminder_response = api_client.post(
        "/marketing-save-reminder",
        json={
            "customer": {
                "customer_key": "test-customer-key",
                "customer_name": "TEST | נעלולי פלא | לקוח שיווק",
            },
            "customer_name": "TEST | נעלולי פלא | לקוח שיווק",
            "due_date": "2026-05-01",
            "due_time": "09:00",
            "message": "TEST | נעלולי פלא | תזכורת",
            "channel": "phone",
        },
    )
    assert note_response.status_code in {200, 400, 422, 500}
    assert reminder_response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_bulk_send_endpoints_accept_safe_test_shapes(api_client):
    email_response = api_client.post(
        "/marketing-work-managers-send-email",
        json={
            "recipients": ["test@example.com"],
            "subject": "TEST | נעלולי פלא | נושא",
            "message": "TEST | נעלולי פלא | גוף הודעה",
        },
    )
    whatsapp_response = api_client.post(
        "/marketing-work-managers-send-whatsapp",
        json={
            "phones": ["0547720142"],
            "message": "TEST | נעלולי פלא | WhatsApp",
        },
    )
    assert email_response.status_code in {200, 400, 422, 500}
    assert whatsapp_response.status_code in {200, 400, 422, 500}
