from __future__ import annotations

from playwright.sync_api import Page

from tests_full_system.helpers.waits import wait_for_visible


class IncomePage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def assert_core_actions_visible(self) -> None:
        for selector in [
            "#incomeCustomerInput",
            "#incomeCustomerLoad",
            "#incomeSummary",
        ]:
            wait_for_visible(self.page, selector)

    def assert_receipts_surface(self) -> None:
        for selector in [
            "#receiptsMode",
            "#receiptsRefresh",
            "#receiptsSummary",
            "#receiptsList",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#receiptsProgress",
            "#receiptsProgressTitle",
            "#receiptsProgressPercent",
            "#receiptsProgressFill",
            "#receiptsProgressMessage",
        ]:
            assert self.page.locator(selector).count() >= 1

    def assert_income_overview_surface(self) -> None:
        for selector in [
            "#incomeCustomerLoad",
            "#incomeCustomerInput",
            "#incomeCustomerReset",
            "#incomeCustomerClear",
            "#incomeDatePreset",
            "#incomeSubmit",
            "#incomeSummary",
            "#incomeKpiTotal",
            "#incomeKpiDocs",
            "#incomeKpiAverage",
            "#incomeKpiTopCustomer",
            "#incomeTableBody",
        ]:
            wait_for_visible(self.page, selector)
        for selector in [
            "#incomeCustomerLoading",
            "#incomeCustomerLoadingFill",
            "#incomeCustomerLoadingLabel",
            "#incomeCustomerDropdown",
            "#incomeCustomerChips",
            "#incomeCustomDates",
            "#incomeStartDate",
            "#incomeEndDate",
            "#incomePieChart",
            "#incomePieLegend",
            "#incomeLineChart",
            "#incomeCustomerBars",
        ]:
            assert self.page.locator(selector).count() >= 1
