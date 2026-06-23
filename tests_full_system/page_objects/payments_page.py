from __future__ import annotations

from playwright.sync_api import Page

from tests_full_system.helpers.waits import wait_for_visible


class PaymentsPage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def assert_core_actions_visible(self) -> None:
        for selector in [
            "#refreshPaymentsTransferButton",
            "#paymentsSearchInput",
            "#paymentsTransfer2026CollectionSummary",
        ]:
            wait_for_visible(self.page, selector)

    def assert_jump_cards_visible(self) -> None:
        wait_for_visible(self.page, '[data-payments-jump="collection"]')
        wait_for_visible(self.page, '[data-payments-jump="payment"]')

    def assert_search_surface(self) -> None:
        for selector in [
            "#paymentsSearchColumn",
            "#paymentsSearchInput",
            "#paymentsSearchClearButton",
            "#paymentsSearchSummary",
            "#paymentsSearchResultsSection",
            "#paymentsSearchResultsSummary",
            "#addPaymentTransferButton",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#paymentsTransferLoading",
            "#paymentsTransferLoadingFill",
            "#paymentsTransferLoadingLabel",
            "#paymentsSearchResultsBody",
        ]:
            assert self.page.locator(selector).count() >= 1

    def assert_collection_and_payment_sections(self) -> None:
        for selector in [
            "#paymentsTransfer2026CollectionSection",
            "#paymentsTransfer2026CollectionSummary",
            "#paymentsTransfer2026CollectionFilterSummary",
            "#paymentsTransfer2026PaymentSection",
            "#paymentsTransfer2026PaymentSummary",
            "#paymentsTransfer2026PaymentFilterSummary",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#paymentsTransfer2026CollectionBody",
            "#paymentsTransfer2026PaymentBody",
        ]:
            assert self.page.locator(selector).count() >= 1

    def open_inline_editor_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const draft = document.getElementById('paymentsTransferDraft');
              if (!draft) return;
              draft.classList.add('visible');
            }
            """
        )
        wait_for_visible(self.page, "#paymentsTransferDraft")

    def assert_inline_editor_surface(self) -> None:
        wait_for_visible(self.page, "#paymentsTransferDraft")

    def assert_filter_buttons_present(self) -> None:
        wait_for_visible(self.page, '[data-payments-filter="collection:paid"]')
        wait_for_visible(self.page, '[data-payments-filter="collection:open"]')
        wait_for_visible(self.page, '[data-payments-filter="collection:overdue"]')
        wait_for_visible(self.page, '[data-payments-filter="payment:paid"]')
        wait_for_visible(self.page, '[data-payments-filter="payment:open"]')
        wait_for_visible(self.page, '[data-payments-filter="payment:overdue"]')
