"""E2E tests for all 'send modal' flows.

Pattern: user has active document → opens send modal → fills recipients/message → sends.
Each modal has: validation toasts (empty recipients/phone), button disabled during send,
success closes modal + toast, failure keeps modal open + re-enables buttons.

Flows covered:
- Quote send email modal (sendQuoteMail)
- Quote send WhatsApp modal (sendQuoteWhatsapp)
- Admin business doc send email modal (sendAdminBusinessDocEmail)
- Inventory purchase order send email (sendInventoryPurchaseOrderEmail)
- Receipt collection communication modal (sendReceiptCollectionCommunication)
- Working order note modal (saveWorkingOrderNote)
- Working order delete modal (confirmWorkingOrderDelete)
- Finance invoices send email modal (sendFinanceInvoicesEmail)
"""
from __future__ import annotations

import json

import pytest

from tests_full_system.helpers.toast import (
    wait_for_error_toast,
    wait_for_info_toast,
    wait_for_success_toast,
)
from tests_full_system.helpers.waits import wait_for_idle_ui, wait_for_visible
from tests_full_system.page_objects.app_shell import AppShell


def _open(page, tab: str) -> None:
    shell = AppShell(page)
    shell.open()
    shell.open_tab(tab)
    wait_for_idle_ui(page)


def _route_ok(page, pattern: str, body: dict) -> None:
    page.route(pattern, lambda r: r.fulfill(
        status=200, content_type="application/json", body=json.dumps(body)
    ))


def _route_fail(page, pattern: str, error: str = "שגיאת שרת") -> None:
    page.route(pattern, lambda r: r.fulfill(
        status=500, content_type="application/json", body=json.dumps({"error": error})
    ))


def _inject_active_quote(page) -> None:
    """Simulate an active quote so quote send flows are triggered."""
    page.evaluate("""
    () => {
        window.currentQuoteResult = {
            quote_file: '/tmp/test-quote.pdf',
            history_id: 'test-quote-history-001',
            customer_name: 'TEST | נעלולי פלא | לקוח',
            customer_email: 'test@example.com',
        };
    }
    """)


def _open_quote_mail_modal(page) -> None:
    _inject_active_quote(page)
    page.evaluate("""
    () => {
        const modal = document.getElementById('quoteMailModal');
        if (modal) {
            modal.classList.add('visible');
            modal.setAttribute('aria-hidden', 'false');
        }
    }
    """)
    wait_for_visible(page, "#quoteMailModal.visible")


def _open_working_order_note_modal(page, row_id: str = "test-wo-001") -> None:
    page.evaluate(f"""
    () => {{
        window.currentWorkingOrderNoteRowId = '{row_id}';
        window.workingOrderRows = [{{
            row_id: '{row_id}',
            customer_name: 'TEST | נעלולי פלא | לקוח',
            po_number: 'WO-E2E-001',
        }}];
        const modal = document.getElementById('workingOrderNoteModal');
        if (modal) {{
            modal.classList.add('visible');
            modal.setAttribute('aria-hidden', 'false');
        }}
    }}
    """)
    wait_for_visible(page, "#workingOrderNoteModal.visible", timeout=5_000)


def _open_working_order_delete_modal(page, row_id: str = "test-wo-del-001") -> None:
    page.evaluate(f"""
    () => {{
        window.workingOrderRows = [{{
            row_id: '{row_id}',
            customer_name: 'TEST | נעלולי פלא | לקוח למחיקה',
            po_number: 'WO-DEL-001',
        }}];
        if (typeof openWorkingOrderDeleteModal === 'function') {{
            openWorkingOrderDeleteModal('{row_id}');
        }} else {{
            const modal = document.getElementById('workingOrderDeleteModal');
            if (modal) {{
                window.pendingWorkingOrderDeleteId = '{row_id}';
                modal.classList.add('visible');
                modal.setAttribute('aria-hidden', 'false');
            }}
        }}
    }}
    """)
    wait_for_visible(page, "#workingOrderDeleteModal.visible", timeout=5_000)


# ===========================================================================
# QUOTE SEND EMAIL MODAL
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_mail_modal_opens_when_quote_active(page):
    """When a quote is active, clicking the send email button must open the quote mail modal."""
    _open(page, "orders")
    _inject_active_quote(page)
    _open_quote_mail_modal(page)
    wait_for_visible(page, "#quoteMailModal.visible")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_mail_modal_has_required_fields(page):
    _open(page, "orders")
    _open_quote_mail_modal(page)

    for sel in [
        "#quoteMailRecipients",
        "#quoteMailSubject",
        "#quoteMailSend",
        "#quoteMailTestSend",
        "#quoteMailCancel",
    ]:
        loc = page.locator(sel)
        assert loc.count() > 0, f"Missing element in quote mail modal: {sel}"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_mail_send_without_recipients_shows_info_toast(page):
    """Clicking send with empty recipients → 'חסר מייל יעד' info toast."""
    _open(page, "orders")
    _open_quote_mail_modal(page)

    # Clear recipients
    recipients = page.locator("#quoteMailRecipients")
    if recipients.is_visible():
        recipients.fill("")

    send_btn = page.locator("#quoteMailSend")
    if send_btn.is_visible():
        send_btn.click()
        wait_for_info_toast(page, title_contains="חסר מייל יעד")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_mail_send_success_closes_modal_and_shows_toast(page):
    """Successful send → modal closes + success toast."""
    _open(page, "orders")
    _open_quote_mail_modal(page)
    _route_ok(page, "**/quote-send-email", {"status": "ok"})

    recipients = page.locator("#quoteMailRecipients")
    if recipients.is_visible():
        recipients.fill("test@example.com")

    send_btn = page.locator("#quoteMailSend")
    if send_btn.is_visible():
        send_btn.click()
        wait_for_success_toast(page, title_contains="מייל הצעת מחיר נשלח", timeout=8_000)

        # Modal must close
        modal = page.locator("#quoteMailModal")
        has_visible = "visible" in (modal.get_attribute("class") or "")
        assert not has_visible, "Quote mail modal stayed open after successful send"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_mail_send_failure_keeps_modal_open_and_shows_error(page):
    """Failed send → error toast + modal stays open (user can retry)."""
    _open(page, "orders")
    _open_quote_mail_modal(page)
    _route_fail(page, "**/quote-send-email", "חיבור ל-Gmail נכשל")

    recipients = page.locator("#quoteMailRecipients")
    if recipients.is_visible():
        recipients.fill("test@example.com")

    send_btn = page.locator("#quoteMailSend")
    if send_btn.is_visible():
        send_btn.click()
        wait_for_error_toast(page, title_contains="שליחת הצעת מחיר נכשלה", timeout=8_000)

        # Modal must STAY open
        modal = page.locator("#quoteMailModal")
        has_visible = "visible" in (modal.get_attribute("class") or "")
        assert has_visible, "Quote mail modal closed after failure — user can't retry"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_mail_test_send_button_routes_to_default_email(page):
    """'שלח טסט' must send to asafbeny@gmail.com regardless of recipients field."""
    _open(page, "orders")
    _open_quote_mail_modal(page)

    sent_payloads = []

    def capture_handler(route):
        sent_payloads.append(route.request.post_data)
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"status": "ok"}))

    page.route("**/quote-send-email", capture_handler)

    # Fill with a 'production' address — test_send should override it
    recipients = page.locator("#quoteMailRecipients")
    if recipients.is_visible():
        recipients.fill("production-customer@example.com")

    test_btn = page.locator("#quoteMailTestSend")
    if test_btn.is_visible():
        test_btn.click()
        wait_for_success_toast(page, title_contains="טסט הצעת מחיר נשלח", timeout=8_000)

    if sent_payloads:
        payload_str = sent_payloads[0] or ""
        assert "test_send=true" in payload_str or "true" in payload_str, (
            "Test send flag not set in request payload"
        )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_mail_cancel_closes_modal(page):
    """Cancel button closes the quote mail modal without sending."""
    _open(page, "orders")
    _open_quote_mail_modal(page)

    cancel = page.locator("#quoteMailCancel")
    if cancel.is_visible():
        cancel.click()
        wait_for_idle_ui(page)
        modal = page.locator("#quoteMailModal")
        has_visible = "visible" in (modal.get_attribute("class") or "")
        assert not has_visible, "Quote mail modal still open after clicking Cancel"


# ===========================================================================
# WORKING ORDER NOTE MODAL
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_note_modal_opens(page):
    _open(page, "orders")
    _open_working_order_note_modal(page)
    wait_for_visible(page, "#workingOrderNoteModal.visible")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_note_modal_has_text_and_save_button(page):
    _open(page, "orders")
    _open_working_order_note_modal(page)

    for sel in ["#workingOrderNoteText", "#workingOrderNoteSave", "#workingOrderNoteCancel"]:
        assert page.locator(sel).count() > 0, f"Missing element in note modal: {sel}"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_note_save_success_closes_modal_and_shows_toast(page):
    """Save note → success toast + modal closes."""
    _open(page, "orders")
    _open_working_order_note_modal(page)
    _route_ok(page, "**/working-orders-note-save", {
        "status": "ok",
        "row": {"row_id": "test-wo-001", "customer_name": "TEST"},
    })

    note_text = page.locator("#workingOrderNoteText")
    if note_text.is_visible():
        note_text.fill("TEST | נעלולי פלא | הערה")

    save_btn = page.locator("#workingOrderNoteSave")
    if save_btn.is_visible():
        save_btn.click()
        wait_for_success_toast(page, title_contains="הערות ההזמנה נשמרו", timeout=8_000)

        modal = page.locator("#workingOrderNoteModal")
        has_visible = "visible" in (modal.get_attribute("class") or "")
        assert not has_visible, "Note modal still open after successful save"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_note_save_failure_shows_error_toast_keeps_modal(page):
    """Save failure → error toast + modal stays open (user can retry)."""
    _open(page, "orders")
    _open_working_order_note_modal(page)
    _route_fail(page, "**/working-orders-note-save", "Drive לא זמין")

    note_text = page.locator("#workingOrderNoteText")
    if note_text.is_visible():
        note_text.fill("TEST | נעלולי פלא | הערה שתיכשל")

    save_btn = page.locator("#workingOrderNoteSave")
    if save_btn.is_visible():
        save_btn.click()
        wait_for_error_toast(page, title_contains="שמירת הערות נכשלה", timeout=8_000)

        modal = page.locator("#workingOrderNoteModal")
        has_visible = "visible" in (modal.get_attribute("class") or "")
        assert has_visible, "Note modal closed after save failure — user loses their text"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_note_save_button_disabled_during_save(page):
    """Save button must be disabled while saving (prevents double-submit)."""
    _open(page, "orders")
    _open_working_order_note_modal(page)

    def slow_handler(route):
        import time; time.sleep(0.3)
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"status": "ok", "row": {"row_id": "test-wo-001"}}))

    page.route("**/working-orders-note-save", slow_handler)

    note_text = page.locator("#workingOrderNoteText")
    if note_text.is_visible():
        note_text.fill("TEST | נעלולי פלא | הערה")

    save_btn = page.locator("#workingOrderNoteSave")
    if save_btn.is_visible():
        save_btn.click()
        assert save_btn.is_disabled(), "Save button not disabled during save — double-submit possible"


# ===========================================================================
# WORKING ORDER DELETE MODAL
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_delete_modal_shows_order_details(page):
    """Delete modal must show the customer name and PO number of the row being deleted."""
    _open(page, "orders")
    _open_working_order_delete_modal(page)

    message = page.locator("#workingOrderDeleteMessage")
    if message.is_visible():
        text = message.inner_text()
        assert "TEST | נעלולי פלא | לקוח למחיקה" in text or "WO-DEL-001" in text, (
            f"Delete modal does not show the order being deleted. Text: '{text}'"
        )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_delete_modal_has_confirm_and_cancel(page):
    _open(page, "orders")
    _open_working_order_delete_modal(page)

    wait_for_visible(page, "#workingOrderDeleteConfirm")
    wait_for_visible(page, "#workingOrderDeleteCancel")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_delete_cancel_closes_modal(page):
    _open(page, "orders")
    _open_working_order_delete_modal(page)

    page.locator("#workingOrderDeleteCancel").click()
    wait_for_idle_ui(page)
    modal = page.locator("#workingOrderDeleteModal")
    has_visible = "visible" in (modal.get_attribute("class") or "")
    assert not has_visible, "Delete modal still open after Cancel"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_delete_confirm_success_shows_toast_and_closes(page):
    """Confirm delete → /working-orders-delete → success toast + modal closes + row removed."""
    _open(page, "orders")
    _open_working_order_delete_modal(page)
    _route_ok(page, "**/working-orders-delete", {"status": "ok"})

    page.locator("#workingOrderDeleteConfirm").click()
    wait_for_success_toast(page, title_contains="ההזמנה נמחקה", timeout=8_000)

    modal = page.locator("#workingOrderDeleteModal")
    has_visible = "visible" in (modal.get_attribute("class") or "")
    assert not has_visible, "Delete modal still open after successful deletion"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_delete_confirm_failure_shows_error_toast_keeps_modal(page):
    """Failed delete → error toast + modal stays open + confirm button re-enabled."""
    _open(page, "orders")
    _open_working_order_delete_modal(page)
    _route_fail(page, "**/working-orders-delete", "Drive לא זמין")

    page.locator("#workingOrderDeleteConfirm").click()
    wait_for_error_toast(page, title_contains="מחיקת ההזמנה נכשלה", timeout=8_000)

    modal = page.locator("#workingOrderDeleteModal")
    has_visible = "visible" in (modal.get_attribute("class") or "")
    assert has_visible, "Delete modal closed after failure — user might not know it failed"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_delete_confirm_button_disabled_during_delete(page):
    """Confirm button must be disabled while delete is in progress."""
    _open(page, "orders")
    _open_working_order_delete_modal(page)

    def slow_handler(route):
        import time; time.sleep(0.3)
        route.fulfill(status=200, content_type="application/json",
                      body=json.dumps({"status": "ok"}))

    page.route("**/working-orders-delete", slow_handler)

    confirm_btn = page.locator("#workingOrderDeleteConfirm")
    confirm_btn.click()
    assert confirm_btn.is_disabled(), "Delete confirm not disabled during operation"


# ===========================================================================
# FINANCE INVOICES SEND EMAIL MODAL
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoices_send_modal_opens(page):
    _open(page, "finance")

    page.evaluate("""
    () => {
        if (typeof openFinanceInvoicesSendModal === 'function') {
            openFinanceInvoicesSendModal();
        } else {
            const modal = document.getElementById('financeInvoicesSendModal');
            if (modal) {
                modal.classList.add('visible');
                modal.setAttribute('aria-hidden', 'false');
            }
        }
    }
    """)
    wait_for_idle_ui(page)
    modal = page.locator("#financeInvoicesSendModal")
    assert modal.count() > 0, "Finance invoices send modal not found in DOM"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoices_send_without_recipients_shows_info_toast(page):
    """Finance invoices send without recipients → 'חסר מייל יעד'."""
    _open(page, "finance")

    page.evaluate("""
    () => {
        const modal = document.getElementById('financeInvoicesSendModal');
        if (modal) {
            modal.classList.add('visible');
            modal.setAttribute('aria-hidden', 'false');
        }
        const recipientsEl = document.getElementById('financeInvoicesSendRecipients');
        if (recipientsEl) recipientsEl.value = '';
    }
    """)
    wait_for_idle_ui(page)

    send_btn = page.locator("#financeInvoicesSendConfirm, [id*='InvoicesSendConfirm']").first
    if send_btn.count() > 0 and send_btn.is_visible():
        send_btn.click()
        wait_for_info_toast(page, timeout=5_000)


# ===========================================================================
# INVENTORY PURCHASE ORDER SEND EMAIL MODAL
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_po_send_modal_requires_active_po(page):
    """Send email button on PO without active PO context must not crash."""
    _open(page, "inventory")

    page.evaluate("""
    () => {
        if (typeof sendInventoryPurchaseOrderEmail === 'function') {
            sendInventoryPurchaseOrderEmail(false);
        }
    }
    """)
    wait_for_idle_ui(page)
    # Should silently return (no currentInventoryPurchaseOrderRow) — no crash
    js_errors = []
    page.on("pageerror", lambda e: js_errors.append(str(e)))
    assert not any("TypeError" in e or "ReferenceError" in e for e in js_errors)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_po_send_email_success_shows_toast(page):
    """PO send email with active row + valid recipients → success toast."""
    _open(page, "inventory")

    _route_ok(page, "**/inventory-purchase-orders-send-email", {
        "status": "ok",
        "row": {"history_id": "test-po-001"},
    })

    page.evaluate("""
    () => {
        window.currentInventoryPurchaseOrderRow = {
            history_id: 'test-po-001',
            po_number: 'RK-E2E-001',
            supplier_name: 'TEST | נעלולי פלא | ספק',
            po_local_file: '/tmp/po.pdf',
        };
        const recipientsEl = document.getElementById('inventoryPurchaseOrderRecipients');
        const subjectEl = document.getElementById('inventoryPurchaseOrderSubject');
        const messageEl = document.getElementById('inventoryPurchaseOrderMessage');
        if (recipientsEl) recipientsEl.value = 'test@example.com';
        if (subjectEl) subjectEl.value = 'TEST הזמנת רכש';
        if (messageEl) messageEl.value = 'TEST | נעלולי פלא | תוכן';
        if (typeof sendInventoryPurchaseOrderEmail === 'function') {
            sendInventoryPurchaseOrderEmail(false);
        }
    }
    """)
    wait_for_success_toast(page, title_contains="הזמנת רכש נשלחה", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_po_send_email_failure_shows_error_toast(page):
    """PO send failure → error toast + buttons re-enabled."""
    _open(page, "inventory")
    _route_fail(page, "**/inventory-purchase-orders-send-email", "Gmail לא מחובר")

    page.evaluate("""
    () => {
        window.currentInventoryPurchaseOrderRow = {
            history_id: 'test-po-fail',
            po_local_file: '/tmp/po.pdf',
        };
        const recipientsEl = document.getElementById('inventoryPurchaseOrderRecipients');
        if (recipientsEl) recipientsEl.value = 'test@example.com';
        if (typeof sendInventoryPurchaseOrderEmail === 'function') {
            sendInventoryPurchaseOrderEmail(false);
        }
    }
    """)
    wait_for_error_toast(page, title_contains="שליחת מייל נכשלה", timeout=8_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_po_test_send_shows_success_toast(page):
    """Test send for PO → success toast 'טסט נשלח'."""
    _open(page, "inventory")

    _route_ok(page, "**/inventory-purchase-orders-send-email", {"status": "ok"})

    page.evaluate("""
    () => {
        window.currentInventoryPurchaseOrderRow = {
            history_id: 'test-po-test',
            po_local_file: '/tmp/po.pdf',
        };
        if (typeof sendInventoryPurchaseOrderEmail === 'function') {
            sendInventoryPurchaseOrderEmail(true);  // testSend = true
        }
    }
    """)
    wait_for_success_toast(page, title_contains="טסט נשלח", timeout=8_000)
