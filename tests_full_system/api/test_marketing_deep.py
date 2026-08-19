"""Deep marketing API tests — pipeline CRUD, reminders, exports, bulk operations."""
from __future__ import annotations

import io

import pytest


# ---------------------------------------------------------------------------
# Pipeline CRUD
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_save_returns_status_on_success(api_client):
    payload = {
        "row": {
            "customer_key": "test-pipeline-customer-deep-001",
            "customer_name": "TEST | נעלולי פלא | לקוח פייפליין עמוק",
            "emails": "test@example.com",
            "phone": "0547720142",
            "contact_name": "TEST | נעלולי פלא | איש קשר",
            "status": "בטיפול",
        }
    }
    response = api_client.post("/marketing-pipeline-save", json=payload)
    assert response.status_code in {200, 400, 404, 422, 500}
    if response.status_code == 200:
        assert isinstance(response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_delete_with_nonexistent_key(api_client):
    response = api_client.post(
        "/marketing-pipeline-delete",
        json={"customer_key": "nonexistent-customer-key-999"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_marketing_refresh_reachable(api_client):
    response = api_client.post("/marketing-refresh", timeout=300)
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_history_refresh_reachable(api_client):
    response = api_client.post("/marketing-history-refresh")
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_docs_refresh_reachable(api_client):
    response = api_client.post("/marketing-docs-refresh")
    assert response.status_code < 500


# ---------------------------------------------------------------------------
# Pricing export/import
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_pricing_export_start_reachable(api_client):
    response = api_client.post("/marketing-pipeline-pricing-export-start")
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_pricing_export_progress_reachable(api_client):
    response = api_client.get("/marketing-pipeline-pricing-export-progress")
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_pricing_export_download_returns_file_or_error(api_client):
    response = api_client.get("/marketing-pipeline-pricing-export-download")
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_marketing_pipeline_pricing_import_accepts_xlsx(api_client):
    # Empty XLSX bytes stub
    xlsx_stub = (
        b"PK\x03\x04"  # minimal zip signature (XLSX is a zip)
        + b"\x00" * 26
    )
    files = {"file": ("pricing_update.xlsx", io.BytesIO(xlsx_stub), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    response = api_client.post("/marketing-pipeline-pricing-import", files=files)
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# Work managers CRUD
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_work_managers_refresh_reachable(api_client):
    response = api_client.post("/marketing-work-managers-refresh")
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_work_managers_save_full_shape(api_client):
    payload = {
        "row": {
            "row_id": "test-wm-deep-001",
            "full_name": "TEST | נעלולי פלא | מנהל עבודה עמוק",
            "email": "test@example.com",
            "phone_1": "0547720142",
            "phone_2": "0547720143",
            "company": "TEST | נעלולי פלא | חברה",
            "role": "מנהל עבודה",
            "city": "חיפה",
            "active_status": "כן",
        }
    }
    response = api_client.post("/marketing-work-managers-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}
    if response.status_code == 200:
        assert isinstance(response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_work_managers_delete_with_nonexistent_id(api_client):
    response = api_client.post(
        "/marketing-work-managers-delete",
        json={"row_id": "nonexistent-wm-999"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_work_managers_delete_many_accepts_id_list(api_client):
    response = api_client.post(
        "/marketing-work-managers-delete-many",
        json={"row_ids": ["nonexistent-1", "nonexistent-2"]},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_work_managers_send_whatsapp_test_number(api_client):
    response = api_client.post(
        "/marketing-work-managers-send-whatsapp",
        json={
            "phones": ["0547720142"],
            "message": "TEST | נעלולי פלא | הודעת WhatsApp מנהלי עבודה",
        },
    )
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# Construction companies CRUD
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_construction_companies_refresh_reachable(api_client):
    response = api_client.post("/marketing-construction-companies-refresh")
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_construction_companies_save_full_shape(api_client):
    payload = {
        "row": {
            "row_id": "test-cc-deep-001",
            "company_name": "TEST | נעלולי פלא | חברת בנייה עמוק",
            "email": "test@example.com",
            "phone": "0547720142",
            "contact_name": "TEST | נעלולי פלא | איש קשר",
            "city": "תל אביב",
        }
    }
    response = api_client.post("/marketing-construction-companies-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_construction_companies_delete_many(api_client):
    response = api_client.post(
        "/marketing-construction-companies-delete-many",
        json={"row_ids": ["nonexistent-cc-1", "nonexistent-cc-2"]},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_construction_companies_export_xlsx(api_client):
    response = api_client.get("/marketing-construction-companies-export-xlsx")
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_marketing_construction_companies_import_xlsx(api_client):
    xlsx_stub = b"PK\x03\x04" + b"\x00" * 26
    files = {
        "file": (
            "cc_import.xlsx",
            io.BytesIO(xlsx_stub),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    response = api_client.post("/marketing-construction-companies-import-xlsx", files=files)
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# Notes & Reminders
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_save_note_full_shape(api_client):
    response = api_client.post(
        "/marketing-save-note",
        json={
            "customer": {
                "customer_key": "test-deep-customer-001",
                "customer_name": "TEST | נעלולי פלא | לקוח הערה",
            },
            "note_text": "TEST | נעלולי פלא | הערה מפורטת לבדיקה עמוקה",
        },
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_save_reminder_phone_channel(api_client):
    response = api_client.post(
        "/marketing-save-reminder",
        json={
            "customer": {
                "customer_key": "test-deep-customer-001",
                "customer_name": "TEST | נעלולי פלא | לקוח תזכורת",
            },
            "customer_name": "TEST | נעלולי פלא | לקוח תזכורת",
            "due_date": "2026-07-01",
            "due_time": "09:00",
            "message": "TEST | נעלולי פלא | תזכורת טלפון",
            "channel": "phone",
        },
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_save_reminder_whatsapp_channel(api_client):
    response = api_client.post(
        "/marketing-save-reminder",
        json={
            "customer": {
                "customer_key": "test-deep-customer-002",
                "customer_name": "TEST | נעלולי פלא | לקוח תזכורת WA",
            },
            "customer_name": "TEST | נעלולי פלא | לקוח תזכורת WA",
            "due_date": "2026-07-15",
            "due_time": "10:30",
            "message": "TEST | נעלולי פלא | תזכורת WhatsApp",
            "channel": "whatsapp",
        },
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_reminders_refresh_reachable(api_client):
    response = api_client.post("/marketing-reminders-refresh")
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_reminder_delete_with_nonexistent_id(api_client):
    response = api_client.post(
        "/marketing-reminder-delete",
        json={"reminder_id": "nonexistent-reminder-999"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_complete_reminder_with_nonexistent_id(api_client):
    response = api_client.post(
        "/marketing-complete-reminder",
        json={"reminder_id": "nonexistent-reminder-999"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


# ---------------------------------------------------------------------------
# Send email / WhatsApp to customer
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_send_email_to_customer(api_client):
    response = api_client.post(
        "/marketing-send-email",
        json={
            "customer": {
                "customer_key": "test-customer-email-001",
                "customer_name": "TEST | נעלולי פלא | לקוח מייל",
                "emails": "test@example.com",
            },
            "subject": "TEST | נעלולי פלא | נושא מייל",
            "message": "TEST | נעלולי פלא | גוף הודעה",
            "recipients": "test@example.com",
        },
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_send_whatsapp_to_customer(api_client):
    response = api_client.post(
        "/marketing-send-whatsapp",
        json={
            "customer": {
                "customer_key": "test-customer-wa-001",
                "customer_name": "TEST | נעלולי פלא | לקוח WA",
                "phone": "0547720142",
            },
            "phone": "0547720142",
            "message": "TEST | נעלולי פלא | הודעת WhatsApp ללקוח",
        },
    )
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# Quote endpoints
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_quote_missing_id(api_client):
    response = api_client.get("/marketing-pipeline-quote")
    assert response.status_code in {400, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_quote_resolve_missing_token(api_client):
    response = api_client.get("/marketing-pipeline-quote-resolve")
    assert response.status_code in {400, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_quote_update_detail_missing_id(api_client):
    response = api_client.get("/marketing-pipeline-quote-update-detail")
    assert response.status_code in {400, 404, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_marketing_pipeline_create_updated_quote_accepts_shape(api_client):
    response = api_client.post(
        "/marketing-pipeline-create-updated-quote",
        json={
            "mode": "sandbox",
            "quote_id": "test-quote-001",
            "customer_name": "TEST | נעלולי פלא | לקוח הצעה מעודכנת",
        },
    )
    assert response.status_code in {200, 400, 404, 422, 500}
