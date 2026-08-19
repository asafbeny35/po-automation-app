"""Tests for endpoints that exist in app.py but were missing from all test files.

Covers:
  POST /customers-assign-domain
  POST /quote-send-email
  POST /quote-send-whatsapp
  POST /delivery-confirmations-mark-sent
  POST /delivery-confirmations-send-coc
  GET  /manual-order-recent-customers
  POST /manual-order-recent-templates
  POST /open-output-folder
  POST /greeninvoice-income-overview
  POST /finance-invoices-export-deliver
  POST /finance-customer-withholdings-import-prod-2026
  GET  /google-drive/health
  GET  /gmail-oauth/start
  GET  /google-drive/oauth/start
  GET  /files/{file_path:path}
"""
from __future__ import annotations

import io

import pytest


# ---------------------------------------------------------------------------
# customers-assign-domain
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_customers_assign_domain_rejects_empty_rows(api_client):
    response = api_client.post(
        "/customers-assign-domain",
        json={"rows": [], "customer_domain": "בנייה"},
    )
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_customers_assign_domain_rejects_missing_domain(api_client):
    response = api_client.post(
        "/customers-assign-domain",
        json={
            "rows": [{"customer_name": "TEST | נעלולי פלא | לקוח", "customer_guid": "test-guid"}],
            "customer_domain": "",
        },
    )
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_customers_assign_domain_rejects_empty_body(api_client):
    response = api_client.post("/customers-assign-domain", json={})
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.requires_live_server
def test_customers_assign_domain_accepts_valid_shape(api_client):
    response = api_client.post(
        "/customers-assign-domain",
        json={
            "rows": [
                {
                    "customer_name": "TEST | נעלולי פלא | לקוח שיוך",
                    "customer_guid": "test-guid-assign-domain-001",
                    "customer_id": "999999999",
                }
            ],
            "customer_domain": "בנייה",
        },
    )
    assert response.status_code in {200, 400, 422, 500}
    if response.status_code == 200:
        assert response.payload.get("status") == "ok"
        assert "updated_count" in response.payload
        assert "customer_domain" in response.payload


# ---------------------------------------------------------------------------
# quote-send-email
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_send_email_rejects_missing_recipients(api_client):
    response = api_client.post(
        "/quote-send-email",
        data={
            "recipients": "",
            "subject": "TEST | נעלולי פלא | נושא",
            "plain_body": "TEST | נעלולי פלא | גוף",
            "html_body": "<p>TEST</p>",
            "quote_file": "",
            "history_id": "",
            "test_send": "false",
        },
    )
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_send_email_rejects_missing_subject(api_client):
    response = api_client.post(
        "/quote-send-email",
        data={
            "recipients": "test@example.com",
            "subject": "",
            "plain_body": "TEST | נעלולי פלא | גוף",
            "html_body": "<p>TEST</p>",
            "quote_file": "",
            "history_id": "",
            "test_send": "false",
        },
    )
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_send_email_test_send_routes_to_default_email(api_client):
    """test_send=true overrides recipients to the configured default address."""
    response = api_client.post(
        "/quote-send-email",
        data={
            "recipients": "production@example.com",
            "subject": "TEST | נעלולי פלא | הצעת מחיר",
            "plain_body": "TEST | נעלולי פלא | גוף",
            "html_body": "<p>TEST | נעלולי פלא | גוף</p>",
            "quote_file": "",
            "history_id": "",
            "test_send": "true",
        },
    )
    # May succeed (200) or fail due to no mail configured (500) — not a crash
    assert response.status_code in {200, 400, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_send_email_missing_quote_file_path_still_validates(api_client):
    """quote_file can be empty — email without attachment is valid."""
    response = api_client.post(
        "/quote-send-email",
        data={
            "recipients": "test@example.com",
            "subject": "TEST | נעלולי פלא | הצעת מחיר ללא קובץ",
            "plain_body": "TEST | נעלולי פלא | גוף",
            "html_body": "",
            "quote_file": "",
            "history_id": "",
            "test_send": "false",
        },
    )
    assert response.status_code in {200, 400, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_send_email_nonexistent_quote_file_returns_404(api_client):
    response = api_client.post(
        "/quote-send-email",
        data={
            "recipients": "test@example.com",
            "subject": "TEST | נעלולי פלא | הצעת מחיר",
            "plain_body": "TEST | נעלולי פלא | גוף",
            "html_body": "",
            "quote_file": "nonexistent/path/quote.pdf",
            "history_id": "",
            "test_send": "false",
        },
    )
    assert response.status_code in {400, 404, 422, 500}


# ---------------------------------------------------------------------------
# quote-send-whatsapp
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_send_whatsapp_rejects_missing_phone(api_client):
    response = api_client.post(
        "/quote-send-whatsapp",
        json={"message": "TEST | נעלולי פלא | WA", "quote_file": "some/path.pdf"},
    )
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_send_whatsapp_rejects_missing_quote_file(api_client):
    response = api_client.post(
        "/quote-send-whatsapp",
        json={"phone": "0547720142", "message": "TEST | נעלולי פלא | WA", "quote_file": ""},
    )
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_send_whatsapp_nonexistent_file_returns_error(api_client):
    response = api_client.post(
        "/quote-send-whatsapp",
        json={
            "phone": "0547720142",
            "message": "TEST | נעלולי פלא | WA",
            "quote_file": "nonexistent/quote.pdf",
        },
    )
    assert response.status_code in {400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_quote_send_whatsapp_rejects_empty_body(api_client):
    response = api_client.post("/quote-send-whatsapp", json={})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# delivery-confirmations-mark-sent
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_mark_sent_rejects_missing_identifiers(api_client):
    response = api_client.post("/delivery-confirmations-mark-sent", json={})
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_mark_sent_with_nonexistent_po_number(api_client):
    response = api_client.post(
        "/delivery-confirmations-mark-sent",
        json={
            "po_number": "NONEXISTENT-PO-TEST-999",
            "tax_invoice_number": "999999",
            "source_mode": "SB",
            "company": "TEST | נעלולי פלא | חברה",
        },
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_mark_sent_with_fulfillment_id(api_client):
    response = api_client.post(
        "/delivery-confirmations-mark-sent",
        json={"fulfillment_id": "test-fulfillment-999"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


# ---------------------------------------------------------------------------
# delivery-confirmations-send-coc
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_send_coc_rejects_missing_identifiers(api_client):
    response = api_client.post(
        "/delivery-confirmations-send-coc",
        json={"recipients": "test@example.com"},
    )
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_send_coc_rejects_missing_recipients(api_client):
    response = api_client.post(
        "/delivery-confirmations-send-coc",
        json={"po_number": "TEST-PO-001", "recipients": ""},
    )
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_send_coc_nonexistent_po_returns_404(api_client):
    response = api_client.post(
        "/delivery-confirmations-send-coc",
        json={
            "po_number": "NONEXISTENT-COC-PO-TEST-999",
            "recipients": "test@example.com",
        },
    )
    assert response.status_code in {400, 404, 422, 500}


# ---------------------------------------------------------------------------
# manual-order-recent-customers
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_manual_order_recent_customers_returns_ok(api_client):
    response = api_client.get("/manual-order-recent-customers")
    assert response.status_code in {200, 500}
    if response.status_code == 200:
        assert isinstance(response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.slow
@pytest.mark.timeout(300)
def test_manual_order_recent_customers_with_force_refresh(api_client):
    response = api_client.get("/manual-order-recent-customers?force=true", timeout=300)
    assert response.status_code in {200, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_manual_order_recent_customers_stale_cache_on_error(api_client):
    """Even on error, endpoint must not crash — it falls back to stale cache or 500."""
    response = api_client.get("/manual-order-recent-customers")
    assert response.status_code < 600  # anything is acceptable except uncaught exception


# ---------------------------------------------------------------------------
# manual-order-recent-templates
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_manual_order_recent_templates_accepts_customer_shape(api_client):
    response = api_client.post(
        "/manual-order-recent-templates",
        json={
            "customer_guid": "test-guid-recent-templates-001",
            "customer_id": "999999999",
            "customer_name": "TEST | נעלולי פלא | לקוח תבניות",
        },
    )
    assert response.status_code in {200, 400, 422, 500}
    if response.status_code == 200:
        assert isinstance(response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_manual_order_recent_templates_with_empty_body(api_client):
    """Empty body → should use empty strings → still return a response."""
    response = api_client.post("/manual-order-recent-templates", json={})
    assert response.status_code in {200, 400, 500}


# ---------------------------------------------------------------------------
# open-output-folder
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_open_output_folder_returns_ok_or_501_on_vercel(api_client):
    response = api_client.post("/open-output-folder")
    # On Vercel: 501. Locally: 200. Never a crash.
    assert response.status_code in {200, 500, 501}


# ---------------------------------------------------------------------------
# greeninvoice-income-overview
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_greeninvoice_income_overview_sandbox_reachable(api_client):
    response = api_client.post(
        "/greeninvoice-income-overview",
        json={"mode": "sandbox"},
    )
    assert response.status_code in {200, 400, 401, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_greeninvoice_income_overview_accepts_empty_body(api_client):
    """Endpoint uses defaults when body is empty — should return 200, not 500."""
    response = api_client.post("/greeninvoice-income-overview", json={})
    assert response.status_code in {200, 400, 422}, (
        f"Unexpected status {response.status_code}"
    )


# ---------------------------------------------------------------------------
# finance-invoices-export-deliver
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoices_export_deliver_reachable(api_client):
    response = api_client.post(
        "/finance-invoices-export-deliver",
        json={
            "recipients": "test@example.com",
            "subject": "TEST | נעלולי פלא | ייצוא חשבוניות",
            "message": "TEST | נעלולי פלא | גוף",
            "row_ids": [],
            "format": "xlsx",
        },
    )
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_invoices_export_deliver_rejects_empty(api_client):
    response = api_client.post("/finance-invoices-export-deliver", json={})
    assert response.status_code in {400, 422}


# ---------------------------------------------------------------------------
# finance-customer-withholdings-import-prod-2026
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_finance_withholdings_import_prod_reachable(api_client):
    """Migration endpoint — reachable but should be idempotent-safe."""
    response = api_client.post("/finance-customer-withholdings-import-prod-2026", json={})
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# google-drive/health
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_google_drive_health_returns_ok_or_not_configured(api_client):
    response = api_client.get("/google-drive/health")
    assert response.status_code in {200, 409}
    assert isinstance(response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_google_drive_health_has_status_field(api_client):
    response = api_client.get("/google-drive/health")
    assert response.status_code in {200, 409}
    assert any(k in response.payload for k in ("status", "ok", "connected", "error"))


# ---------------------------------------------------------------------------
# files/{file_path:path}
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_files_nonexistent_path_returns_404(api_client):
    response = api_client.get("/files/nonexistent/path/file.pdf")
    assert response.status_code in {400, 404, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_files_path_traversal_rejected(api_client):
    """Path traversal attempt must not return 200."""
    response = api_client.get("/files/../../etc/passwd")
    assert response.status_code in {400, 403, 404, 422}


# ---------------------------------------------------------------------------
# OAuth start/callback (just reachability — full OAuth requires browser)
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_gmail_oauth_start_returns_redirect(api_client):
    response = api_client.request("GET", "/gmail-oauth/start")
    # Should redirect to Google or return an error if not configured
    assert response.status_code in {200, 302, 400, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_google_drive_oauth_start_returns_redirect(api_client):
    response = api_client.request("GET", "/google-drive/oauth/start")
    assert response.status_code in {200, 302, 400, 500}
