from __future__ import annotations

from playwright.sync_api import Page

from tests_full_system.helpers.waits import wait_for_idle_ui, wait_for_visible


class OrdersPage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def open_manual_entry(self) -> None:
        wait_for_visible(self.page, "#manualEntryPanel")

    def assert_core_actions_visible(self) -> None:
        for selector in [
            "#manualLoadButton",
            "#manualClearButton",
            "#orderHistoryLoadButton",
            "#quoteHistoryLoadButton",
            "#dropZone",
            "#resetButton",
            "#openOutputButton",
        ]:
            wait_for_visible(self.page, selector)
        assert self.page.locator("#transportLabelPanel").count() >= 1

    def assert_manual_fields_visible(self) -> None:
        for selector in [
            "#manualPoNumber",
            "#manualPoDate",
            "#manualCustomerName",
            "#manualCustomerId",
            "#manualPaymentTermsDays",
            "#manualCustomerPhonePrefix",
            "#manualCustomerPhoneRest",
            "#manualCustomerEmail",
            "#manualDeliveryAddress",
            "#manualProject",
            "#manualContactName",
            "#manualContactPhonePrefix",
            "#manualContactPhoneRest",
            "#manualItemSku",
            "#manualItemDescription",
            "#manualItemQuantity",
            "#manualItemUnit",
            "#manualItemUnitPrice",
            "#manualVat",
            "#manualTotal",
            "#manualFooterText",
            "#manualAddItemButton",
            "#manualLabelSplitButton",
        ]:
            wait_for_visible(self.page, selector)

    def switch_to_quote_mode(self) -> None:
        self.page.locator("#manualModeQuoteButton").click()
        wait_for_idle_ui(self.page)

    def switch_to_order_mode(self) -> None:
        self.page.locator("#manualModeOrderButton").click()
        wait_for_idle_ui(self.page)

    def toggle_partial_delivery(self) -> None:
        self.page.locator("#manualPartialDeliveryCheckbox").check()
        wait_for_idle_ui(self.page)

    def clear_manual_form(self) -> None:
        self.page.locator("#manualClearButton").click()
        wait_for_idle_ui(self.page)

    def fill_minimal_manual_order(self, *, quantity: str = "1") -> None:
        self.page.locator("#manualPoNumber").fill("TEST-E2E-ORDER")
        self.page.locator("#manualPoDate").fill("2026-05-01")
        self.page.locator("#manualCustomerName").fill("TEST | נעלולי פלא | לקוח E2E")
        self.page.locator("#manualCustomerId").fill("999999999")
        self.page.locator("#manualDeliveryAddress").fill("כתובת TEST 1")
        self.page.locator("#manualItemDescription").fill("TEST | נעלולי פלא | מוצר")
        self.page.locator("#manualItemQuantity").fill(quantity)
        self.page.locator("#manualItemUnitPrice").fill("100")
        wait_for_idle_ui(self.page)

    def load_manual_order_to_screen(self) -> None:
        self.page.locator("#manualLoadButton").click()
        wait_for_idle_ui(self.page)

    def assert_partial_delivery_confirmation_modal(self) -> None:
        wait_for_visible(self.page, "#partialDeliveryConfirmModal")

    def open_label_split_modal(self) -> None:
        self.page.locator("#manualLabelSplitButton").click()
        wait_for_visible(self.page, "#labelSplitModal")

    def open_order_history_panel(self) -> None:
        if self.page.locator("#orderHistoryOpenButton:visible").count() == 0 and self.page.locator("#orderHistoryPanelBackButton:visible").count() > 0:
            self.page.locator("#orderHistoryPanelBackButton").click()
            wait_for_idle_ui(self.page)
        self.page.locator("#orderHistoryOpenButton").click()
        self.page.locator("#orderHistoryRowsHost").wait_for(state="attached", timeout=10_000)

    def open_quote_history_panel(self) -> None:
        if self.page.locator("#quoteHistoryOpenButton:visible").count() == 0:
            if self.page.locator("#orderHistoryPanelBackButton:visible").count() > 0:
                self.page.locator("#orderHistoryPanelBackButton").click()
                wait_for_idle_ui(self.page)
            elif self.page.locator("#quoteHistoryPanelBackButton:visible").count() > 0:
                self.page.locator("#quoteHistoryPanelBackButton").click()
                wait_for_idle_ui(self.page)
        self.page.locator("#quoteHistoryOpenButton").click()
        self.page.locator("#quoteHistoryRowsHost").wait_for(state="attached", timeout=10_000)

    def assert_creation_buttons_grouped(self) -> None:
        wait_for_visible(self.page, ".create-actions-group.sandbox")
        wait_for_visible(self.page, ".create-actions-group.prod")

    def assert_progress_bar_present(self) -> None:
        assert self.page.locator("#progressWrap").count() >= 1

    def assert_history_widgets_visible(self) -> None:
        for selector in [
            "#orderHistoryWidgetTitle",
            "#orderHistoryLoadButton",
            "#orderHistoryRecentSummary",
            "#orderHistoryOpenButton",
            "#quoteHistoryWidget",
            "#quoteHistoryWidgetTitle",
            "#quoteHistoryLoadButton",
            "#quoteHistoryRecentSummary",
            "#quoteHistoryOpenButton",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#orderHistoryRecentHost",
            "#orderHistoryWidgetProgress",
            "#orderHistoryWidgetProgressTitle",
            "#orderHistoryWidgetProgressPercent",
            "#orderHistoryWidgetProgressFill",
            "#orderHistoryWidgetProgressMessage",
            "#quoteHistoryRecentHost",
            "#quoteHistoryWidgetProgress",
            "#quoteHistoryWidgetProgressTitle",
            "#quoteHistoryWidgetProgressPercent",
            "#quoteHistoryWidgetProgressFill",
            "#quoteHistoryWidgetProgressMessage",
        ]:
            assert self.page.locator(selector).count() >= 1

    def assert_order_history_panel_surfaces(self) -> None:
        for selector in [
            "#orderHistoryPanelBackButton",
            "#orderHistoryPanelLoadButton",
            "#orderHistorySummary",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#orderHistoryRowsHost",
            "#orderHistoryPanelProgress",
            "#orderHistoryPanelProgressTitle",
            "#orderHistoryPanelProgressPercent",
            "#orderHistoryPanelProgressFill",
            "#orderHistoryPanelProgressMessage",
        ]:
            assert self.page.locator(selector).count() >= 1

    def assert_quote_history_panel_surfaces(self) -> None:
        for selector in [
            "#quoteHistoryPanelBackButton",
            "#quoteHistoryPanelLoadButton",
            "#quoteHistorySummary",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#quoteHistoryRowsHost",
            "#quoteHistoryPanelProgress",
            "#quoteHistoryPanelProgressTitle",
            "#quoteHistoryPanelProgressPercent",
            "#quoteHistoryPanelProgressFill",
            "#quoteHistoryPanelProgressMessage",
        ]:
            assert self.page.locator(selector).count() >= 1
        self.page.locator("#quoteHistorySignedUploadInput").wait_for(state="attached", timeout=10_000)

    def open_order_history_delete_modal_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const modal = document.getElementById('orderHistoryDeleteModal');
              const title = document.getElementById('orderHistoryDeleteTitle');
              const message = document.getElementById('orderHistoryDeleteMessage');
              if (!modal) return;
              if (title) title.textContent = 'מחיקת היסטוריית הזמנה';
              if (message) message.textContent = 'למחוק את הרשומה הזו מההיסטוריה?';
              modal.classList.add('visible');
              modal.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#orderHistoryDeleteModal")

    def assert_order_history_delete_modal_surface(self) -> None:
        for selector in [
            "#orderHistoryDeleteTitle",
            "#orderHistoryDeleteMessage",
            "#orderHistoryDeleteCancel",
            "#orderHistoryDeleteConfirm",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#orderHistoryDeleteProgress",
            "#orderHistoryDeleteProgressTitle",
            "#orderHistoryDeleteProgressPercent",
            "#orderHistoryDeleteProgressFill",
            "#orderHistoryDeleteProgressMessage",
        ]:
            assert self.page.locator(selector).count() >= 1
