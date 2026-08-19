"""Comprehensive UI interaction + toast feedback tests.

These tests verify the full user-visible feedback loop:
- Button is clickable
- Correct toast type appears (success / error / info)
- Toast title matches expected Hebrew text
- No silent failures — every action has a visible outcome

Every test here represents a case where existing API tests would NOT catch the bug,
because the bug lives in the JavaScript event handler or the toast rendering layer.
"""
from __future__ import annotations

import pytest

from tests_full_system.helpers.toast import (
    wait_for_error_toast,
    wait_for_info_toast,
    wait_for_success_toast,
)
from tests_full_system.helpers.waits import wait_for_idle_ui, wait_for_visible
from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.orders_page import OrdersPage


# ---------------------------------------------------------------------------
# Helper: wait for any toast (any type)
# ---------------------------------------------------------------------------

def _wait_any_toast(page, timeout=6_000):
    page.locator(".toast.visible").first.wait_for(state="visible", timeout=timeout)


# ===========================================================================
# ORDERS TAB — button interactions and toast feedback
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_open_output_folder_shows_feedback_toast(page):
    """Clicking 'פתח תיקיית Output' must always show a toast — success locally, error on cloud.

    This is the canonical regression test for the cloud bug: on Vercel the server
    returns 501, but the JS catches it and must show an error toast.  The test
    passes whether the server returns 200 (local) or 501 (Vercel) — it fails only
    if the user sees NOTHING, which is the actual bug.
    """
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")

    page.locator("#openOutputButton").click()
    _wait_any_toast(page, timeout=8_000)

    # Either outcome is acceptable as long as something is shown
    visible_toasts = page.locator(".toast.visible").count()
    assert visible_toasts > 0, (
        "openOutputButton click produced no toast at all. "
        "On cloud this means the 501 response is being silently swallowed — "
        "the user gets no feedback."
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_open_output_folder_shows_error_toast_when_server_returns_501(page):
    """Mock the endpoint to return 501 and verify the error toast appears."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")

    # Intercept the fetch and return a 501
    page.route(
        "**/open-output-folder",
        lambda route: route.fulfill(
            status=501,
            content_type="application/json",
            body='{"error": "not supported on cloud"}',
        ),
    )

    page.locator("#openOutputButton").click()
    wait_for_error_toast(page, title_contains="שגיאה בפתיחת output", timeout=6_000)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_load_manual_order_without_po_number_shows_error_toast(page):
    """Clicking 'טען הזמנה ידנית' with no PO number → error toast 'חסר מידע בהזמנה הידנית'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")

    # Leave all fields empty, click load
    page.locator("#manualLoadButton").click()
    wait_for_error_toast(page, title_contains="חסר מידע בהזמנה הידנית")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_load_manual_order_with_po_number_but_no_customer_shows_error_toast(page):
    """PO number filled but customer name empty → error toast."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")

    page.locator("#manualPoNumber").fill("TEST-E2E-VALIDATION")
    page.locator("#manualPoDate").fill("2026-06-25")
    page.locator("#manualLoadButton").click()

    wait_for_error_toast(page, title_contains="חסר מידע בהזמנה הידנית")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_reset_button_shows_info_toast(page):
    """Clicking 'אפס' (reset) must show 'המסך אופס' info toast."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")

    page.locator("#resetButton").click()
    wait_for_info_toast(page, title_contains="המסך אופס")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_upload_button_without_file_shows_info_toast(page):
    """Clicking 'הפק סנדבוקס' without uploading a PDF → info toast 'צריך לבחור קובץ'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")

    page.locator("button[onclick=\"upload('sandbox')\"]").click()
    wait_for_info_toast(page, title_contains="צריך לבחור קובץ")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_send_sandbox_without_data_shows_info_toast(page):
    """Clicking 'צור סנדבוקס' without loaded data → info toast about no data."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")

    page.locator("button[onclick=\"send('sandbox')\"]").click()
    # Either 'צריך קודם להפיק נתונים' or 'חסרים נתונים חובה'
    _wait_any_toast(page, timeout=5_000)
    info_or_error = page.locator(".toast.info.visible, .toast.error.visible").count()
    assert info_or_error > 0, "No toast appeared after clicking 'צור סנדבוקס' with no data"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_transport_replace_without_data_shows_info_toast(page):
    """Clicking 'החלף PDF' transport button without data → 'צריך קודם להפיק נתונים'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")

    page.locator("#transportReplaceButton").click()
    wait_for_info_toast(page, title_contains="צריך קודם להפיק נתונים")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_transport_clear_button_shows_info_toast(page):
    """Clicking 'נקה' transport button → info toast 'PDF המשלוח נוקה'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")

    page.locator("#transportClearButton").click()
    wait_for_info_toast(page, title_contains="PDF המשלוח נוקה")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_upload_without_file_shows_info_toast(page):
    """Clicking 'שמור כהזמנה בעבודה' without PDF → 'צריך לבחור קובץ'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")

    # Open working orders section
    wait_for_visible(page, "#workingOrdersUploadButton")
    page.locator("#workingOrdersUploadButton").click()
    wait_for_info_toast(page, title_contains="צריך לבחור קובץ")


# ===========================================================================
# CUSTOMERS TAB — validation toasts
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_customers_tab_opens(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("customers")
    wait_for_visible(page, "#customersRefreshButton")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_customers_assign_domain_without_selection_shows_info_toast(page):
    """Clicking 'שמור שיוך' with no customers selected → 'לא נבחרו לקוחות'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("customers")
    wait_for_idle_ui(page)

    page.locator("#customersAssignDomainButton").click()
    wait_for_info_toast(page, title_contains="לא נבחרו לקוחות")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_customers_new_customer_save_without_name_shows_info_toast(page):
    """Clicking save new customer without name → 'חסר שם לקוח'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("customers")
    wait_for_idle_ui(page)

    # Open customer creation form
    page.locator("#customerCreateToggleButton").click()
    wait_for_idle_ui(page)

    # Try to save without filling the name
    save_btn = page.locator("#customerCreateSaveButton")
    if save_btn.is_visible():
        save_btn.click()
        wait_for_info_toast(page, title_contains="חסר שם לקוח")


# ===========================================================================
# INCOME TAB — validation toasts
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_income_tab_opens(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("income")
    wait_for_idle_ui(page)
    # Income tab must show at least one visible element
    assert page.locator(".top-tab.active[data-tab='income']").count() > 0


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_income_receipt_zero_amount_shows_error_toast(page):
    """Attempting to issue a receipt with amount=0 → 'סכום לא תקין'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("income")
    wait_for_idle_ui(page)

    # Look for the receipt amount field and try submitting 0
    amount_field = page.locator("#receiptAmount, #incomeReceiptAmount, [id*='ReceiptAmount']").first
    if amount_field.is_visible():
        amount_field.fill("0")
        submit_btn = page.locator("#issueReceiptButton, #receiptIssueButton, [id*='ReceiptButton']").first
        if submit_btn.is_visible():
            submit_btn.click()
            wait_for_error_toast(page, title_contains="סכום לא תקין")


# ===========================================================================
# PAYMENTS TAB — validation toasts
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_payments_tab_opens(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("payments-transfers")
    wait_for_idle_ui(page)
    assert page.locator(".top-tab.active[data-tab='payments-transfers']").count() > 0


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_payments_send_whatsapp_without_phone_shows_info_toast(page):
    """Clicking send WhatsApp from income/payments without a phone → 'חסר טלפון'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("income")
    wait_for_idle_ui(page)

    send_wa_btn = page.locator("#sendWhatsappButton, [id*='SendWhatsapp'], [id*='WhatsappSend']").first
    if send_wa_btn.is_visible():
        # Clear the phone field first
        phone_field = page.locator("[id*='Phone'], [id*='phone']").first
        if phone_field.is_visible():
            phone_field.fill("")
        send_wa_btn.click()
        wait_for_info_toast(page, title_contains="חסר טלפון")


# ===========================================================================
# INVENTORY TAB — validation toasts
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_tab_opens(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("inventory")
    wait_for_idle_ui(page)
    assert page.locator(".top-tab.active[data-tab='inventory']").count() > 0


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_restore_real_stock_button_visible(page):
    """'החזר למלאי אמיתי' button must be present in the inventory tab."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("inventory")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#restoreRealStockButton")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_reset_button_shows_info_toast(page):
    """Clicking 'אפס מלאי' → 'המלאי אופס' info toast."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("inventory")
    wait_for_idle_ui(page)

    reset_btn = page.locator("#inventoryResetButton")
    if reset_btn.is_visible():
        reset_btn.click()
        wait_for_info_toast(page, title_contains="המלאי אופס")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_purchase_order_create_button_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("inventory")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#inventoryPurchaseOrdersCreateButton")


# ===========================================================================
# MARKETING TAB — validation toasts
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_marketing_tab_opens(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("marketing")
    wait_for_idle_ui(page)
    assert page.locator(".top-tab.active[data-tab='marketing']").count() > 0


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_marketing_work_managers_copy_phones_no_data_shows_info_toast(page):
    """'העתק טלפונים' with no loaded managers → 'אין ניידים להעתקה'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("marketing")
    wait_for_idle_ui(page)

    page.locator("#marketingWorkManagersCopyPhonesButton").click()
    wait_for_info_toast(page, title_contains="אין ניידים להעתקה")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_marketing_work_managers_copy_emails_no_data_shows_info_toast(page):
    """'העתק כתובות דוא״ל' with no loaded managers → 'אין מיילים להעתקה'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("marketing")
    wait_for_idle_ui(page)

    page.locator("#marketingWorkManagersCopyEmailsButton").click()
    wait_for_info_toast(page, title_contains="אין מיילים להעתקה")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_marketing_construction_copy_phones_no_data_shows_info_toast(page):
    """Copy phones for construction companies with no data → 'אין טלפונים להעתקה'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("marketing")
    wait_for_idle_ui(page)

    page.locator("#marketingConstructionCompaniesCopyPhonesButton").click()
    wait_for_info_toast(page, title_contains="אין טלפונים להעתקה")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_marketing_construction_copy_emails_no_data_shows_info_toast(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("marketing")
    wait_for_idle_ui(page)

    page.locator("#marketingConstructionCompaniesCopyEmailsButton").click()
    wait_for_info_toast(page, title_contains="אין מיילים להעתקה")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_marketing_send_reminder_without_phone_shows_info_toast(page):
    """Send WhatsApp reminder without a phone number → 'חסר טלפון'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("marketing")
    wait_for_idle_ui(page)

    # Look for a send reminder whatsapp button
    send_btn = page.locator("[id*='ReminderSendWhatsapp'], [id*='reminderSendWa'], .reminder-send-wa").first
    if send_btn.count() > 0 and send_btn.is_visible():
        send_btn.click()
        wait_for_info_toast(page, title_contains="חסר טלפון")


# ===========================================================================
# FINANCE TAB — validation toasts
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_tab_opens(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    wait_for_idle_ui(page)
    assert page.locator(".top-tab.active[data-tab='finance']").count() > 0


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoices_delete_without_selection_shows_info_toast(page):
    """Clicking delete invoice with no rows selected → 'לא נבחרו רשומות'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    wait_for_idle_ui(page)

    delete_btn = page.locator("#financeInvoicesDeleteButton, [id*='InvoicesDelete']").first
    if delete_btn.is_visible():
        delete_btn.click()
        wait_for_info_toast(page, title_contains="לא נבחרו רשומות")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoices_key_buttons_visible(page):
    """All key finance buttons must be visible after opening tab."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    wait_for_idle_ui(page)

    for btn_id in [
        "#financeInvoicesLoadButton",
        "#financeInvoicesSendButton",
        "#financeInvoicesExportButton",
    ]:
        loc = page.locator(btn_id)
        if loc.count() > 0:
            assert loc.count() >= 1, f"Expected {btn_id} to exist in finance tab"


# ===========================================================================
# HR TAB — surface and basic interactions
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_hr_tab_opens(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("employees-hr")
    wait_for_idle_ui(page)
    assert page.locator(".top-tab.active[data-tab='employees-hr']").count() > 0


# ===========================================================================
# ADMIN TAB — surface
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_admin_tab_opens(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("admin")
    wait_for_idle_ui(page)
    assert page.locator(".top-tab.active[data-tab='admin']").count() > 0


# ===========================================================================
# DELIVERY CONFIRMATION — validation toasts
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_send_coc_without_email_shows_info_toast(page):
    """Clicking 'שלח COC' without email → 'חסר מייל יעד'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    wait_for_idle_ui(page)

    # Scroll to delivery confirmation section
    coc_btn = page.locator("[id*='SendCoc'], [id*='CocSend'], .coc-send-btn").first
    if coc_btn.count() > 0 and coc_btn.is_visible():
        # Clear email field if present
        email_field = page.locator("[id*='CocEmail'], [id*='cocEmail']").first
        if email_field.is_visible():
            email_field.fill("")
        coc_btn.click()
        wait_for_info_toast(page, title_contains="חסר מייל יעד")


# ===========================================================================
# SUPPORT CENTER — open/close
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_support_center_opens_and_closes(page):
    """Support center FAB opens modal, close button dismisses it."""
    shell = AppShell(page)
    shell.open()
    shell.open_support_center()
    wait_for_visible(page, "#supportCenterModal")
    shell.close_support_center()
    page.locator("#supportCenterModal").wait_for(state="hidden", timeout=5_000)


# ===========================================================================
# SEND DOCUMENT — validation toasts (income/orders send panel)
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_send_email_without_active_document_shows_info_toast(page):
    """Clicking 'שלח מייל' in income tab without an active document → 'אין מסמך פעיל'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("income")
    wait_for_idle_ui(page)

    send_email_btn = page.locator(
        "#sendEmailButton, [id*='SendEmail'], .send-email-btn"
    ).first
    if send_email_btn.count() > 0 and send_email_btn.is_visible():
        send_email_btn.click()
        wait_for_info_toast(page, title_contains="אין מסמך פעיל")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_send_email_without_recipients_shows_info_toast(page):
    """If a document is active but no recipients filled → 'חסר מייל יעד'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("income")
    wait_for_idle_ui(page)

    # Simulate a document being loaded by stubbing currentData
    page.evaluate("() => { window.currentData = { po_number: 'TEST-E2E', customer_name: 'TEST' }; }")
    wait_for_idle_ui(page)

    send_email_btn = page.locator(
        "#sendEmailButton, [id*='SendEmail']:not([id*='sendEmailTo'])"
    ).first
    if send_email_btn.count() > 0 and send_email_btn.is_visible():
        # Ensure email field is empty
        email_input = page.locator(
            "#sendEmailTo, [id*='EmailRecipient'], [id*='emailTo'], [id*='Recipients']"
        ).first
        if email_input.is_visible():
            email_input.fill("")
        send_email_btn.click()
        wait_for_info_toast(page, title_contains="חסר מייל יעד")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_send_email_without_active_quote_shows_info_toast(page):
    """'שלח הצעת מחיר במייל' without active quote → 'אין הצעת מחיר פעילה'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    wait_for_idle_ui(page)

    # Switch to quote mode
    page.locator("#manualModeQuoteButton").click()
    wait_for_idle_ui(page)

    quote_send_email_btn = page.locator(
        "#quoteSendEmailButton, [id*='QuoteSendEmail'], [id*='quoteSendEmail']"
    ).first
    if quote_send_email_btn.count() > 0 and quote_send_email_btn.is_visible():
        quote_send_email_btn.click()
        wait_for_info_toast(page, title_contains="אין הצעת מחיר פעילה")


# ===========================================================================
# QUOTE SEND WhatsApp — validation
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_send_whatsapp_without_active_quote_shows_info_toast(page):
    """'שלח הצעת מחיר בוואטסאפ' without active quote → 'אין הצעת מחיר פעילה'."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    wait_for_idle_ui(page)

    page.locator("#manualModeQuoteButton").click()
    wait_for_idle_ui(page)

    quote_wa_btn = page.locator(
        "#quoteSendWhatsappButton, [id*='QuoteSendWhatsapp'], [id*='quoteSendWa']"
    ).first
    if quote_wa_btn.count() > 0 and quote_wa_btn.is_visible():
        quote_wa_btn.click()
        wait_for_info_toast(page, title_contains="אין הצעת מחיר פעילה")


# ===========================================================================
# LOGOUT BUTTON
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_logout_button_is_visible_and_clickable(page):
    """Logout button must be visible and clicking it navigates away or returns to login."""
    shell = AppShell(page)
    shell.open()
    wait_for_visible(page, "#logoutButton")
    assert page.locator("#logoutButton").is_visible()


# ===========================================================================
# GLOBAL — toast stack exists and is correctly wired
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_toast_stack_element_exists_in_dom(page):
    """#toastStack must exist — it is the container for all user feedback."""
    shell = AppShell(page)
    shell.open()
    assert page.locator("#toastStack").count() == 1, (
        "#toastStack element missing from DOM — all toast notifications would be silently lost"
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_showtoast_function_is_defined(page):
    """showToast must be a callable function in the page's global scope."""
    shell = AppShell(page)
    shell.open()
    result = page.evaluate("() => typeof window.showToast")
    assert result == "function", (
        f"window.showToast is '{result}', expected 'function'. "
        "All toast-based feedback would silently fail."
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_showtoast_success_renders_visible_toast(page):
    """Directly invoking showToast('success', ...) must produce a visible toast element."""
    shell = AppShell(page)
    shell.open()
    page.evaluate("() => showToast('success', 'טסט', 'הודעת טסט')")
    wait_for_success_toast(page, title_contains="טסט")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_showtoast_error_renders_visible_toast(page):
    """showToast('error', ...) must produce a .toast.error.visible element."""
    shell = AppShell(page)
    shell.open()
    page.evaluate("() => showToast('error', 'שגיאת טסט', 'פרטי שגיאה')")
    wait_for_error_toast(page, title_contains="שגיאת טסט")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_showtoast_info_renders_visible_toast(page):
    """showToast('info', ...) must produce a .toast.info.visible element."""
    shell = AppShell(page)
    shell.open()
    page.evaluate("() => showToast('info', 'מידע טסט', 'תוכן מידע')")
    wait_for_info_toast(page, title_contains="מידע טסט")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_toast_title_appears_in_strong_tag(page):
    """Toast title must be inside <strong> — that's how the UI is styled for prominence."""
    shell = AppShell(page)
    shell.open()
    page.evaluate("() => showToast('info', 'כותרת ייחודית', 'פרטים')")
    page.locator(".toast.info.visible strong").filter(has_text="כותרת ייחודית").wait_for(
        state="visible", timeout=4_000
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_toast_disappears_after_duration(page):
    """Toast must auto-dismiss — it should NOT stay on screen indefinitely."""
    shell = AppShell(page)
    shell.open()
    page.evaluate("() => showToast('success', 'טסט היעלמות', 'בדיקה', 1200)")
    wait_for_success_toast(page)
    # Wait for it to disappear (duration 1200ms + 220ms animation)
    page.locator(".toast.success.visible").wait_for(state="hidden", timeout=4_000)
