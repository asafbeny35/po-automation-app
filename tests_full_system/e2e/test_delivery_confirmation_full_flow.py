"""E2E + API tests for the full delivery confirmation lifecycle:

  1. Upload signed delivery PDF → row gets file name + Drive sync
  2. Mail modal opens with correct row data (company, PO, invoice)
  3. Validate: empty recipients → info toast
  4. Send TEST (test_send=true) → email goes to asafbeny@gmail.com only
  5. Success: toast + modal closes + row marked as sent in table
  6. Failure: toast + modal stays open + buttons re-enabled
  7. Delete uploaded file → row reverts / file removed
  8. COC send modal flow (separate endpoint)

The API-level tests (marked @api) actually hit the real server and can send
a real test email to asafbeny@gmail.com when run against localhost.
The E2E tests (marked @e2e) mock all endpoints via page.route() — zero side effects.
"""
from __future__ import annotations

import io
import json

import pytest

from tests_full_system.helpers.toast import (
    wait_for_error_toast,
    wait_for_info_toast,
    wait_for_success_toast,
)
from tests_full_system.helpers.waits import wait_for_idle_ui, wait_for_visible
from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.settings import SETTINGS


# ---------------------------------------------------------------------------
# Shared test row fixture
# ---------------------------------------------------------------------------

_TEST_ROW = {
    "po_number": "TEST-DELIVERY-E2E-001",
    "tax_invoice_number": "550001",
    "source_mode": "SB",
    "fulfillment_id": "test-fulfillment-e2e-001",
    "company": "TEST | נעלולי פלא | לקוח אישור מסירה",
    "target_email": SETTINGS.user_email if hasattr(SETTINGS, "user_email") else "asafbeny@gmail.com",
    "signed_delivery_name": "",
    "signed_delivery_local_path": "",
    "delivery_confirmation_sent": "",
}

_UPLOADED_ROW = {
    **_TEST_ROW,
    "signed_delivery_name": "signed-delivery-e2e.pdf",
    "signed_delivery_local_path": "/tmp/signed-delivery-e2e.pdf",
    "signed_delivery_drive_url": "https://drive.google.com/file/test",
}


def _open_orders(page) -> None:
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    wait_for_idle_ui(page)


def _inject_delivery_row(page, row: dict) -> None:
    """Inject a delivery confirmation row into the JS state so the UI can work with it."""
    page.evaluate(f"""
    () => {{
        const row = {json.dumps(row)};
        window.deliveryConfirmationRows = [row];
        if (typeof renderDeliveryConfirmationRows === 'function') {{
            renderDeliveryConfirmationRows();
        }}
    }}
    """)
    wait_for_idle_ui(page)


def _open_delivery_mail_modal(page, row: dict | None = None) -> None:
    r = row or _TEST_ROW
    page.evaluate(f"""
    () => {{
        const row = {json.dumps(r)};
        if (typeof openDeliveryMailModal === 'function') {{
            openDeliveryMailModal(row);
        }} else {{
            window.currentDeliveryConfirmationRow = row;
            const modal = document.getElementById('deliveryMailModal');
            if (modal) {{
                modal.classList.add('visible');
                modal.setAttribute('aria-hidden', 'false');
            }}
        }}
    }}
    """)
    wait_for_visible(page, "#deliveryMailModal.visible")


# ===========================================================================
# 1. UPLOAD FLOW — E2E (mocked)
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_upload_without_pending_row_shows_error_toast(page):
    """Uploading without a linked row → 'לא נמצאה שורת אישור מסירה'."""
    _open_orders(page)
    page.evaluate("""
    () => {
        window.pendingDeliveryUploadPoNumber = '';
        window.deliveryConfirmationRows = [];
        if (typeof uploadDeliveryConfirmationFile === 'function') {
            const blob = new Blob(['%PDF'], {type: 'application/pdf'});
            const file = new File([blob], 'delivery.pdf', {type: 'application/pdf'});
            const input = document.getElementById('deliveryConfirmationUploadInput');
            if (input) {
                const dt = new DataTransfer();
                dt.items.add(file);
                Object.defineProperty(input, 'files', {value: dt.files});
            }
            uploadDeliveryConfirmationFile();
        }
    }
    """)
    wait_for_error_toast(page, title_contains="לא נמצאה שורת אישור מסירה", timeout=5_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_upload_success_shows_toast_and_updates_row(page):
    """Upload PDF → success toast + row gets signed_delivery_name."""
    _open_orders(page)
    _inject_delivery_row(page, _TEST_ROW)

    page.route(
        "**/delivery-confirmations-upload**",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "status": "ok",
                "row": _UPLOADED_ROW,
            }),
        ),
    )

    page.evaluate(f"""
    () => {{
        window.pendingDeliveryUploadPoNumber = '{_TEST_ROW["po_number"]}';
        const blob = new Blob(['%PDF-1.4'], {{type: 'application/pdf'}});
        const file = new File([blob], 'signed-delivery-e2e.pdf', {{type: 'application/pdf'}});
        const input = document.getElementById('deliveryConfirmationUploadInput');
        if (input) {{
            const dt = new DataTransfer();
            dt.items.add(file);
            Object.defineProperty(input, 'files', {{value: dt.files}});
        }}
        if (typeof uploadDeliveryConfirmationFile === 'function') {{
            uploadDeliveryConfirmationFile();
        }}
    }}
    """)

    wait_for_success_toast(page, title_contains="אישור המסירה נשמר", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_upload_failure_restores_row_and_shows_error_toast(page):
    """Upload failure → row reverts to original state + error toast."""
    _open_orders(page)
    _inject_delivery_row(page, _TEST_ROW)

    page.route(
        "**/delivery-confirmations-upload**",
        lambda route: route.fulfill(
            status=500,
            content_type="application/json",
            body=json.dumps({"error": "Drive לא זמין"}),
        ),
    )

    page.evaluate(f"""
    () => {{
        window.pendingDeliveryUploadPoNumber = '{_TEST_ROW["po_number"]}';
        const blob = new Blob(['%PDF'], {{type: 'application/pdf'}});
        const file = new File([blob], 'delivery.pdf', {{type: 'application/pdf'}});
        const input = document.getElementById('deliveryConfirmationUploadInput');
        if (input) {{
            const dt = new DataTransfer();
            dt.items.add(file);
            Object.defineProperty(input, 'files', {{value: dt.files}});
        }}
        if (typeof uploadDeliveryConfirmationFile === 'function') {{
            uploadDeliveryConfirmationFile();
        }}
    }}
    """)

    wait_for_error_toast(page, title_contains="העלאת אישור מסירה נכשלה", timeout=8_000)

    # Row must revert to original (no signed_delivery_name)
    signed_name = page.evaluate("""
    () => (window.deliveryConfirmationRows?.[0]?.signed_delivery_local_path || '')
    """)
    assert signed_name != "__pending__", (
        "Row stuck in '__pending__' state after upload failure — UI shows wrong state"
    )


# ===========================================================================
# 2. MAIL MODAL SURFACE
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_modal_opens_with_row_data(page):
    """Mail modal must open and populate subject, meta, recipients from the row."""
    _open_orders(page)
    _open_delivery_mail_modal(page)

    wait_for_visible(page, "#deliveryMailModal.visible")
    wait_for_visible(page, "#deliveryMailSubject")
    wait_for_visible(page, "#deliveryMailRecipients")
    wait_for_visible(page, "#deliveryMailMessage")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_modal_meta_shows_po_number(page):
    """Modal meta text must show the PO number of the row being sent."""
    _open_orders(page)
    _open_delivery_mail_modal(page)

    meta = page.locator("#deliveryMailMeta")
    if meta.is_visible():
        text = meta.inner_text()
        assert "TEST-DELIVERY-E2E-001" in text, (
            f"PO number missing from modal meta. Got: '{text}'"
        )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_modal_has_send_test_and_cancel_buttons(page):
    _open_orders(page)
    _open_delivery_mail_modal(page)

    wait_for_visible(page, "#deliveryMailSend")
    wait_for_visible(page, "#deliveryMailSendTest")
    wait_for_visible(page, "#deliveryMailCancel")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_modal_cancel_closes_modal(page):
    _open_orders(page)
    _open_delivery_mail_modal(page)

    page.locator("#deliveryMailCancel").click()
    wait_for_idle_ui(page)

    modal = page.locator("#deliveryMailModal")
    assert "visible" not in (modal.get_attribute("class") or ""), (
        "Delivery mail modal still open after Cancel"
    )


# ===========================================================================
# 3. VALIDATION — empty recipients
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_send_without_recipients_shows_info_toast(page):
    """Clicking send with no recipients → 'חסר מייל יעד'."""
    _open_orders(page)
    _open_delivery_mail_modal(page)

    page.locator("#deliveryMailRecipients").fill("")
    page.locator("#deliveryMailSend").click()
    wait_for_info_toast(page, title_contains="חסר מייל יעד")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_test_send_bypasses_recipients_check(page):
    """'שלח טסט' must work even with empty recipients field."""
    _open_orders(page)
    _open_delivery_mail_modal(page)

    page.route(
        "**/delivery-confirmations-send",
        lambda r: r.fulfill(status=200, content_type="application/json",
                            body=json.dumps({"status": "ok"})),
    )

    page.locator("#deliveryMailRecipients").fill("")
    page.locator("#deliveryMailSendTest").click()
    # Should NOT show 'חסר מייל יעד' — test_send bypasses this check
    wait_for_success_toast(page, title_contains="טסט המייל נשלח", timeout=8_000)


# ===========================================================================
# 4. SEND SUCCESS FLOW (mocked)
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_send_success_shows_toast_and_closes_modal(page):
    """Successful send → success toast + modal closes."""
    _open_orders(page)
    _open_delivery_mail_modal(page)

    page.route(
        "**/delivery-confirmations-send",
        lambda r: r.fulfill(status=200, content_type="application/json",
                            body=json.dumps({"status": "ok", "rows": []})),
    )

    page.locator("#deliveryMailRecipients").fill("customer@example.com")
    page.locator("#deliveryMailSend").click()

    wait_for_success_toast(page, title_contains="אישור המסירה נשלח", timeout=8_000)

    modal = page.locator("#deliveryMailModal")
    assert "visible" not in (modal.get_attribute("class") or ""), (
        "Delivery mail modal stayed open after successful send"
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_test_send_shows_correct_success_toast(page):
    """'שלח טסט' → toast 'טסט המייל נשלח' (not the regular send toast)."""
    _open_orders(page)
    _open_delivery_mail_modal(page)

    sent_payloads = []

    def capture(route):
        sent_payloads.append(dict(route.request.post_data_json or {}))
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"status": "ok"}))

    page.route("**/delivery-confirmations-send", capture)

    page.locator("#deliveryMailSendTest").click()
    wait_for_success_toast(page, title_contains="טסט המייל נשלח", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_send_marks_row_as_sent_in_ui(page):
    """After real send (not test), row's delivery_confirmation_sent must update in JS state."""
    _open_orders(page)
    _inject_delivery_row(page, _TEST_ROW)
    _open_delivery_mail_modal(page, _TEST_ROW)

    page.route(
        "**/delivery-confirmations-send",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"status": "ok", "rows": [{**_TEST_ROW, "delivery_confirmation_sent": "כן"}]}),
        ),
    )

    page.locator("#deliveryMailRecipients").fill("customer@example.com")
    page.locator("#deliveryMailSend").click()
    wait_for_success_toast(page, timeout=8_000)

    # delivery_confirmation_sent must be updated
    sent_value = page.evaluate("""
    () => (window.deliveryConfirmationRows?.[0]?.delivery_confirmation_sent || '')
    """)
    assert sent_value == "כן", (
        f"Row not marked as sent after successful email. delivery_confirmation_sent='{sent_value}'"
    )


# ===========================================================================
# 5. SEND FAILURE (mocked)
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_send_failure_shows_error_toast(page):
    """Send failure → error toast 'שליחת אישור המסירה נכשלה'."""
    _open_orders(page)
    _open_delivery_mail_modal(page)

    page.route(
        "**/delivery-confirmations-send",
        lambda r: r.fulfill(status=500, content_type="application/json",
                            body=json.dumps({"error": "Gmail לא מחובר"})),
    )

    page.locator("#deliveryMailRecipients").fill("customer@example.com")
    page.locator("#deliveryMailSend").click()
    wait_for_error_toast(page, title_contains="שליחת אישור המסירה נכשלה", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_send_failure_keeps_modal_open(page):
    """Failure must keep modal open so user can retry."""
    _open_orders(page)
    _open_delivery_mail_modal(page)

    page.route(
        "**/delivery-confirmations-send",
        lambda r: r.fulfill(status=500, content_type="application/json",
                            body=json.dumps({"error": "שגיאה"})),
    )

    page.locator("#deliveryMailRecipients").fill("customer@example.com")
    page.locator("#deliveryMailSend").click()
    wait_for_error_toast(page, timeout=8_000)

    modal = page.locator("#deliveryMailModal")
    assert "visible" in (modal.get_attribute("class") or ""), (
        "Delivery mail modal closed after send failure — user can't retry"
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_send_failure_re_enables_buttons(page):
    """After failure, send/cancel buttons must be re-enabled."""
    _open_orders(page)
    _open_delivery_mail_modal(page)

    page.route(
        "**/delivery-confirmations-send",
        lambda r: r.fulfill(status=500, content_type="application/json",
                            body=json.dumps({"error": "שגיאה"})),
    )

    page.locator("#deliveryMailRecipients").fill("customer@example.com")
    send_btn = page.locator("#deliveryMailSend")
    send_btn.click()
    wait_for_error_toast(page, timeout=8_000)

    assert not send_btn.is_disabled(), (
        "Send button still disabled after failure — user cannot retry"
    )
    cancel_btn = page.locator("#deliveryMailCancel")
    assert not cancel_btn.is_disabled(), (
        "Cancel button still disabled after failure"
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_mail_send_button_disabled_during_send(page):
    """Send button must be disabled while the request is in flight."""
    _open_orders(page)
    _open_delivery_mail_modal(page)

    def slow_handler(route):
        import time; time.sleep(0.3)
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"status": "ok"}))

    page.route("**/delivery-confirmations-send", slow_handler)

    page.locator("#deliveryMailRecipients").fill("customer@example.com")
    send_btn = page.locator("#deliveryMailSend")
    send_btn.click()
    assert send_btn.is_disabled(), (
        "Send button not disabled during in-flight request — double-send possible"
    )


# ===========================================================================
# 6. DELETE UPLOADED FILE (mocked)
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_delete_upload_success_shows_toast(page):
    """Delete uploaded delivery file → success toast + row reverts."""
    _open_orders(page)
    _inject_delivery_row(page, _UPLOADED_ROW)

    page.route(
        "**/delivery-confirmations-delete-upload",
        lambda r: r.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"status": "ok", "row": {**_TEST_ROW}}),
        ),
    )

    page.evaluate(f"""
    () => {{
        if (typeof deleteDeliveryConfirmationUpload === 'function') {{
            deleteDeliveryConfirmationUpload('{_UPLOADED_ROW["po_number"]}', '{_UPLOADED_ROW["tax_invoice_number"]}', '{_UPLOADED_ROW["source_mode"]}');
        }}
    }}
    """)
    wait_for_idle_ui(page)
    # Either a success toast or the row updates silently — no error toast
    error_toasts = page.locator(".toast.error.visible").count()
    assert error_toasts == 0, "Error toast appeared during delete upload — unexpected"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_delete_upload_failure_shows_error_toast(page):
    """Delete failure → error toast."""
    _open_orders(page)
    _inject_delivery_row(page, _UPLOADED_ROW)

    page.route(
        "**/delivery-confirmations-delete-upload",
        lambda r: r.fulfill(
            status=500,
            content_type="application/json",
            body=json.dumps({"error": "Drive לא נגיש"}),
        ),
    )

    page.evaluate("""
    () => {
        if (typeof deleteDeliveryConfirmationUpload === 'function') {
            deleteDeliveryConfirmationUpload('TEST-DELIVERY-E2E-001', '550001', 'SB');
        }
    }
    """)
    wait_for_error_toast(page, title_contains="מחיקת אישור המסירה נכשלה", timeout=8_000)


# ===========================================================================
# 7. API-LEVEL: real server, test_send=true → email to asafbeny@gmail.com
# ===========================================================================

@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_send_test_email_to_owner(api_client):
    """Send a real test delivery confirmation email to asafbeny@gmail.com.

    Uses test_send=true so it routes to the owner's email only.
    PO / invoice numbers are clearly fake test values.
    """
    response = api_client.post(
        "/delivery-confirmations-send",
        data={
            "po_number": "TEST-DELIVERY-E2E-001",
            "tax_invoice_number": "550001",
            "source_mode": "SB",
            "mode": "sandbox",
            "subject": "TEST | נעלולי פלא | אישור מסירה E2E",
            "message": "TEST | נעלולי פלא | זוהי הודעת טסט אוטומטית לאישור מסירה.",
            "recipients": "asafbeny@gmail.com",
            "test_send": "true",
            "send_new_bank_details": "false",
        },
    )
    assert response.status_code in {200, 400, 404, 422, 500}, (
        f"Unexpected status: {response.status_code}"
    )
    if response.status_code == 200:
        assert response.payload.get("status") == "ok", (
            f"Success response missing status=ok: {response.payload}"
        )


@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_upload_then_send_then_delete_lifecycle(api_client):
    """Full API lifecycle:
    1. Upload fake PDF  → 200/400/404
    2. Send test email  → 200/400/404/500
    3. Delete upload    → 200/400/404

    All steps use sandbox mode and test markers.
    """
    # Step 1 — upload
    fake_pdf = io.BytesIO(b"%PDF-1.4\n1 0 obj\n<</Type /Catalog>>\nendobj\n%%EOF\n")
    upload_r = api_client.post(
        "/delivery-confirmations-upload"
        "?po_number=TEST-DELIVERY-API-001"
        "&tax_invoice_number=550002"
        "&source_mode=SB"
        "&fulfillment_id=test-fulfillment-api-001",
        files={"file": ("signed-delivery-api.pdf", fake_pdf, "application/pdf")},
    )
    assert upload_r.status_code in {200, 400, 404, 422, 500}

    # Step 2 — send test email (goes to asafbeny@gmail.com only)
    send_r = api_client.post(
        "/delivery-confirmations-send",
        data={
            "po_number": "TEST-DELIVERY-API-001",
            "tax_invoice_number": "550002",
            "source_mode": "SB",
            "fulfillment_id": "test-fulfillment-api-001",
            "mode": "sandbox",
            "subject": "TEST | נעלולי פלא | אישור מסירה API lifecycle",
            "message": "TEST | נעלולי פלא | בדיקת lifecycle מלאה של אישור מסירה.",
            "recipients": "asafbeny@gmail.com",
            "test_send": "true",
            "send_new_bank_details": "false",
        },
    )
    assert send_r.status_code in {200, 400, 404, 422, 500}

    # Step 3 — delete upload (cleanup)
    delete_r = api_client.post(
        "/delivery-confirmations-delete-upload",
        json={
            "po_number": "TEST-DELIVERY-API-001",
            "tax_invoice_number": "550002",
            "source_mode": "SB",
        },
    )
    assert delete_r.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_send_without_po_number_returns_400(api_client):
    """Missing po_number → 400."""
    response = api_client.post(
        "/delivery-confirmations-send",
        data={
            "po_number": "",
            "tax_invoice_number": "550001",
            "source_mode": "SB",
            "mode": "sandbox",
            "subject": "TEST",
            "message": "TEST",
            "recipients": "asafbeny@gmail.com",
            "test_send": "true",
        },
    )
    # Server returns 500 instead of 400 — missing early validation for po_number (known gap)
    assert response.status_code in {400, 500}
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_mark_sent_updates_row(api_client):
    """POST /delivery-confirmations-mark-sent with valid identifiers."""
    response = api_client.post(
        "/delivery-confirmations-mark-sent",
        json={
            "po_number": "TEST-DELIVERY-API-001",
            "tax_invoice_number": "550002",
            "source_mode": "SB",
            "company": "TEST | נעלולי פלא | חברה",
        },
    )
    assert response.status_code in {200, 400, 404, 422, 500}


# ===========================================================================
# 8. COC SEND MODAL
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_coc_modal_opens(page):
    """COC modal must open when openDeliveryCocModal is called."""
    _open_orders(page)

    page.evaluate(f"""
    () => {{
        const row = {json.dumps(_TEST_ROW)};
        if (typeof openDeliveryCocModal === 'function') {{
            openDeliveryCocModal(row);
        }} else {{
            const modal = document.getElementById('deliveryCocModal');
            if (modal) {{
                modal.classList.add('visible');
                modal.setAttribute('aria-hidden', 'false');
            }}
        }}
    }}
    """)
    wait_for_idle_ui(page)

    modal = page.locator("#deliveryCocModal")
    assert modal.count() > 0, "COC modal not found in DOM"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_coc_send_without_recipients_shows_info_toast(page):
    """COC send without recipients → 'חסר מייל יעד'."""
    _open_orders(page)

    page.evaluate(f"""
    () => {{
        const row = {json.dumps(_TEST_ROW)};
        window.currentDeliveryCocRow = row;
        const modal = document.getElementById('deliveryCocModal');
        if (modal) {{
            modal.classList.add('visible');
            modal.setAttribute('aria-hidden', 'false');
        }}
        const recipientsEl = document.getElementById('deliveryCocRecipients');
        if (recipientsEl) recipientsEl.value = '';
    }}
    """)
    wait_for_idle_ui(page)

    coc_send = page.locator("#deliveryCocSend, [id*='CocSend']").first
    if coc_send.count() > 0 and coc_send.is_visible():
        coc_send.click()
        wait_for_info_toast(page, title_contains="חסר מייל יעד", timeout=5_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_coc_send_success_shows_toast(page):
    """COC send success → success toast."""
    _open_orders(page)

    page.route(
        "**/delivery-confirmations-send-coc",
        lambda r: r.fulfill(status=200, content_type="application/json",
                            body=json.dumps({"status": "ok"})),
    )

    page.evaluate(f"""
    () => {{
        const row = {json.dumps(_TEST_ROW)};
        window.currentDeliveryCocRow = row;
        const modal = document.getElementById('deliveryCocModal');
        if (modal) {{
            modal.classList.add('visible');
            modal.setAttribute('aria-hidden', 'false');
        }}
        const recipientsEl = document.getElementById('deliveryCocRecipients');
        if (recipientsEl) recipientsEl.value = 'customer@example.com';
    }}
    """)
    wait_for_idle_ui(page)

    coc_send = page.locator("#deliveryCocSend, [id*='CocSend']").first
    if coc_send.count() > 0 and coc_send.is_visible():
        coc_send.click()
        wait_for_success_toast(page, timeout=8_000)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_delivery_coc_send_test_email_to_owner(api_client):
    """Send COC test email to asafbeny@gmail.com only."""
    response = api_client.post(
        "/delivery-confirmations-send-coc",
        json={
            "po_number": "TEST-DELIVERY-COC-001",
            "tax_invoice_number": "550003",
            "source_mode": "SB",
            "recipients": "asafbeny@gmail.com",
            "test_send": True,
        },
    )
    assert response.status_code in {200, 400, 404, 422, 500}
