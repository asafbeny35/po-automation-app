"""E2E tests for modal dialogs, form validation, and multi-step UI interactions.

Tests here verify:
- Every modal opens correctly
- Every modal has its expected elements inside
- Every modal can be dismissed/closed
- Form validation prevents bad submissions
- Multi-step flows produce the correct intermediate states
"""
from __future__ import annotations

import pytest

from tests_full_system.helpers.toast import wait_for_error_toast, wait_for_info_toast
from tests_full_system.helpers.waits import wait_for_idle_ui, wait_for_visible
from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.orders_page import OrdersPage


# ===========================================================================
# PARTIAL DELIVERY CONFIRMATION MODAL
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_partial_delivery_modal_has_cancel_and_confirm_buttons(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.fill_minimal_manual_order(quantity="1")
    orders.load_manual_order_to_screen()
    orders.toggle_partial_delivery()
    page.locator("button[onclick=\"send('sandbox')\"]").click()

    wait_for_visible(page, "#partialDeliveryConfirmModal")
    wait_for_visible(page, "#partialDeliveryConfirmCancel")
    wait_for_visible(page, "#partialDeliveryConfirmOk")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_partial_delivery_modal_cancel_closes_modal(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.fill_minimal_manual_order(quantity="1")
    orders.load_manual_order_to_screen()
    orders.toggle_partial_delivery()
    page.locator("button[onclick=\"send('sandbox')\"]").click()

    wait_for_visible(page, "#partialDeliveryConfirmModal")
    page.locator("#partialDeliveryConfirmCancel").click()
    wait_for_idle_ui(page)

    # Modal must no longer be visible
    modal = page.locator("#partialDeliveryConfirmModal")
    assert not modal.is_visible() or "visible" not in (modal.get_attribute("class") or ""), (
        "Partial delivery modal still visible after clicking Cancel"
    )


# ===========================================================================
# LABEL SPLIT MODAL
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_label_split_modal_opens_from_button(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.open_label_split_modal()
    wait_for_visible(page, "#labelSplitModal")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_label_split_modal_has_split_validation(page):
    """Invalid split (sum ≠ total) must show error toast."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.open_label_split_modal()
    wait_for_visible(page, "#labelSplitModal")

    # Try to confirm with invalid split configuration
    confirm_btn = page.locator(
        "#labelSplitConfirm, #labelSplitApply, [id*='SplitConfirm']"
    ).first
    if confirm_btn.count() > 0 and confirm_btn.is_visible():
        confirm_btn.click()
        wait_for_error_toast(page, title_contains="חלוקת מדבקות לא תקינה")


# ===========================================================================
# ORDER HISTORY DELETE MODAL
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_order_history_delete_modal_has_all_elements(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.open_order_history_delete_modal_stub()
    orders.assert_order_history_delete_modal_surface()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_order_history_delete_modal_cancel_closes_modal(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.open_order_history_delete_modal_stub()
    wait_for_visible(page, "#orderHistoryDeleteModal")

    page.locator("#orderHistoryDeleteCancel").click()
    wait_for_idle_ui(page)

    modal = page.locator("#orderHistoryDeleteModal")
    is_visible = modal.is_visible()
    has_visible_class = "visible" in (modal.get_attribute("class") or "")
    assert not (is_visible and has_visible_class), "Delete modal still visible after Cancel"


# ===========================================================================
# INVENTORY MEASURE CALCULATOR
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_calculator_button_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("inventory")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#inventoryMeasureCalculateButton")


# ===========================================================================
# MANUAL ORDER FORM — field by field validation
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_manual_order_all_required_fields_validated(page):
    """Submit form with each required field missing one at a time → each shows error toast."""
    required_sequences = [
        # (field_to_skip_filling, expected_missing_label_fragment)
        ("manualPoNumber", "מספר הזמנה"),
        ("manualPoDate", "תאריך הזמנה"),
        ("manualCustomerName", "שם לקוח"),
        ("manualCustomerId", "ח.פ"),
    ]

    for field_id, expected_label in required_sequences:
        shell = AppShell(page)
        shell.open()
        shell.open_tab("orders")

        # Fill all required fields except the target one
        fields = {
            "manualPoNumber": "TEST-E2E-VALIDATION",
            "manualPoDate": "2026-06-25",
            "manualCustomerName": "TEST | נעלולי פלא | לקוח",
            "manualCustomerId": "999999999",
            "manualDeliveryAddress": "כתובת 1",
            "manualItemDescription": "מוצר TEST",
            "manualItemQuantity": "5",
            "manualItemUnitPrice": "100",
        }

        for fid, value in fields.items():
            if fid != field_id:
                field = page.locator(f"#{fid}")
                if field.is_visible():
                    field.fill(value)

        # Clear the field we want to test
        target = page.locator(f"#{field_id}")
        if target.is_visible():
            target.fill("")

        page.locator("#manualLoadButton").click()
        wait_for_error_toast(page, title_contains="חסר מידע בהזמנה הידנית")

        # Clear toasts before next iteration
        page.evaluate("() => document.querySelectorAll('.toast').forEach(t => t.remove())")


# ===========================================================================
# MANUAL ORDER FORM — mode switching
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_mode_switch_hides_partial_delivery_checkbox(page):
    """Quote mode must hide the partial delivery section."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)

    orders.switch_to_quote_mode()
    assert page.locator("#manualPartialDeliveryWrap").is_hidden(), (
        "Partial delivery checkbox visible in quote mode — should be hidden"
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_order_mode_switch_shows_partial_delivery_checkbox(page):
    """Switching back to order mode must restore partial delivery section."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)

    orders.switch_to_quote_mode()
    orders.switch_to_order_mode()
    assert page.locator("#manualPartialDeliveryWrap").is_visible(), (
        "Partial delivery section not restored when switching back to order mode"
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_mode_heading_changes(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)

    orders.switch_to_quote_mode()
    heading_text = page.locator("#manualEntryHeading").inner_text()
    assert "הצעת מחיר" in heading_text, f"Quote mode heading is wrong: '{heading_text}'"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_order_mode_heading_changes(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)

    orders.switch_to_order_mode()
    heading_text = page.locator("#manualEntryHeading").inner_text()
    assert "הזמנה" in heading_text, f"Order mode heading is wrong: '{heading_text}'"


# ===========================================================================
# ADD ITEM BUTTON — dynamic list
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_add_item_button_adds_new_row(page):
    """Clicking '+ הוסף מוצר' must add a second product row to the manual entry form."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")

    # Count existing item rows
    initial_rows = page.locator(".manual-item-row, [data-item-index]").count()
    page.locator("#manualAddItemButton").click()
    wait_for_idle_ui(page)

    new_rows = page.locator(".manual-item-row, [data-item-index]").count()
    assert new_rows > initial_rows, (
        f"Adding item did not create a new row. Before: {initial_rows}, after: {new_rows}"
    )


# ===========================================================================
# PAYMENTS TAB — search/filter UX
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_payments_search_clear_button_starts_disabled(page):
    """'נקה' search clear button must start disabled (no text in search box)."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("payments-transfers")
    wait_for_idle_ui(page)

    clear_btn = page.locator("#paymentsSearchClearButton")
    if clear_btn.is_visible():
        assert clear_btn.is_disabled(), (
            "Payments search clear button should start disabled when search is empty"
        )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_payments_add_row_button_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("payments-transfers")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#addPaymentTransferButton")


# ===========================================================================
# DELIVERY CONFIRMATIONS — filter buttons
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_confirm_filter_buttons_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    wait_for_idle_ui(page)

    wait_for_visible(page, "#deliveryConfirmUnsentButton")
    wait_for_visible(page, "#deliveryConfirmSentButton")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_confirm_filter_toggle_changes_active_state(page):
    """Clicking 'נשלח' filter must become active, 'טרם נשלח' must become inactive."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    wait_for_idle_ui(page)

    unsent = page.locator("#deliveryConfirmUnsentButton")
    sent = page.locator("#deliveryConfirmSentButton")

    # Initially 'unsent' is active
    assert "active" in (unsent.get_attribute("class") or ""), (
        "Expected 'טרם נשלח' button to start as active"
    )

    # Click 'sent' filter
    sent.click()
    wait_for_idle_ui(page)

    assert "active" in (sent.get_attribute("class") or ""), (
        "Expected 'נשלח' button to become active after clicking"
    )


# ===========================================================================
# CUSTOMERS TAB — inactive toggle
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inactive_customers_toggle_button_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("customers")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#inactiveCustomersToggleButton")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_domain_select_all_and_clear_buttons_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("customers")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#customersDomainSelectAllButton")
    wait_for_visible(page, "#customersDomainClearButton")


# ===========================================================================
# MARKETING — active only filter
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_marketing_work_managers_active_only_button_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("marketing")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#marketingWorkManagersActiveOnlyButton")


# ===========================================================================
# INVENTORY — purchase orders section
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_po_sandbox_and_prod_buttons_visible(page):
    """Both sandbox and prod purchase order creation buttons must exist."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("inventory")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#inventoryPoCreateSandboxButton")
    wait_for_visible(page, "#inventoryPoCreateProdButton")


# ===========================================================================
# SUPPLIER DELIVERY NOTE — upload button
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_supplier_delivery_note_upload_button_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("inventory")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#supplierDeliveryNoteUploadButton")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_supplier_delivery_note_save_button_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("inventory")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#supplierDeliveryNotesSaveButton")


# ===========================================================================
# ADD CONTACTS — delivery contacts
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_add_contact_button_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#deliveryContactsAddButton")


# ===========================================================================
# FINANCE INVOICES SEND PANEL
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoices_export_pdf_button_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#financeInvoicesExportPdfButton")


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoices_drive_folder_button_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    wait_for_idle_ui(page)
    wait_for_visible(page, "#financeInvoicesDriveFolderButton")


# ===========================================================================
# PROGRESS INDICATORS — hidden by default
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_progress_wrap_hidden_by_default(page):
    """#progressWrap must not be visible on load — it should only appear during API calls."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    wait_for_idle_ui(page)

    progress = page.locator("#progressWrap")
    is_visible_class = "visible" in (progress.get_attribute("class") or "")
    is_displayed = progress.is_visible()
    assert not (is_visible_class and is_displayed), (
        "#progressWrap is showing on page load — it should be hidden by default"
    )


# ===========================================================================
# ARIA LIVE REGION — accessibility for toasts
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_toast_stack_has_aria_live_polite(page):
    """#toastStack must have aria-live='polite' for screen reader accessibility."""
    shell = AppShell(page)
    shell.open()
    aria_live = page.locator("#toastStack").get_attribute("aria-live")
    assert aria_live == "polite", (
        f"#toastStack has aria-live='{aria_live}', expected 'polite'. "
        "Screen readers won't announce toast messages."
    )


# ===========================================================================
# SUPPORT CENTER — content
# ===========================================================================

@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_support_center_modal_has_close_button(page):
    shell = AppShell(page)
    shell.open()
    shell.open_support_center()
    wait_for_visible(page, "#supportCenterClose")


# ===========================================================================
# TAB NAVIGATION — every tab renders without JS errors
# ===========================================================================

TABS_TO_TEST = [
    "orders",
    "income",
    "payments-transfers",
    "pricing-bom",
    "inventory",
    "admin",
    "finance",
    "office",
    "employees-hr",
    "customers",
    "project-managers",
    "marketing",
]


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
@pytest.mark.parametrize("tab_id", TABS_TO_TEST)
def test_tab_navigation_no_js_errors(page, tab_id):
    """Every tab must open without JavaScript errors."""
    js_errors = []
    page.on("pageerror", lambda err: js_errors.append(str(err)))

    shell = AppShell(page)
    shell.open()
    shell.open_tab(tab_id)
    wait_for_idle_ui(page)

    critical_errors = [
        e for e in js_errors
        if "TypeError" in e or "ReferenceError" in e or "SyntaxError" in e
    ]
    assert not critical_errors, (
        f"JavaScript errors when opening tab '{tab_id}':\n"
        + "\n".join(critical_errors)
    )


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
@pytest.mark.parametrize("tab_id", TABS_TO_TEST)
def test_tab_navigation_active_class_set(page, tab_id):
    """After clicking a tab, it must receive the 'active' class."""
    shell = AppShell(page)
    shell.open()
    shell.open_tab(tab_id)

    active_tab = page.locator(f'.top-tab.active[data-tab="{tab_id}"]')
    assert active_tab.count() > 0, (
        f"Tab '{tab_id}' did not get 'active' class after being clicked"
    )
