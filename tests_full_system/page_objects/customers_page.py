from __future__ import annotations

from playwright.sync_api import Page

from tests_full_system.helpers.waits import wait_for_idle_ui, wait_for_visible


class CustomersPage:
    def __init__(self, page: Page) -> None:
        self.page = page

    def assert_core_actions_visible(self) -> None:
        for selector in [
            "#customersRefreshButton",
            "#customersDriveRefreshButton",
            "#customersSummary",
        ]:
            wait_for_visible(self.page, selector)

    def assert_list_surface(self) -> None:
        for selector in [
            "#customersSummary",
            "#customersAlphaNav",
            "#inactiveCustomersToggleButton",
            "#inactiveCustomersSummary",
        ]:
            wait_for_visible(self.page, selector)
        assert self.page.locator("#customersList").count() >= 1

    def assert_inactive_list_surface(self) -> None:
        assert self.page.locator("#inactiveCustomersList").count() >= 1

    def assert_create_form_surface(self) -> None:
        if self.page.locator("#customerCreateName").count() and not self.page.locator("#customerCreateName").first.is_visible():
            self.page.locator("#customerCreateToggleButton").click()
            wait_for_idle_ui(self.page)
        for selector in [
            "#customerCreateToggleButton",
            "#customerCreateName",
            "#customerCreateIdNumber",
            "#customerCreatePaymentTerms",
            "#customerCreatePhone",
            "#customerCreateMobile",
            "#customerCreateContactPerson",
            "#customerCreateEmails",
            "#customerCreateDepartment",
            "#customerCreateCountry",
            "#customerCreateAddress",
            "#customerCreateCity",
            "#customerCreateZip",
            "#customerCreateRemarks",
            "#customerCreateSubmit",
        ]:
            wait_for_visible(self.page, selector)

    def toggle_inactive_archive(self) -> None:
        self.page.locator("#inactiveCustomersToggleButton").click()
        wait_for_idle_ui(self.page)

    def show_selection_toolbar_stub(self) -> None:
        self.page.evaluate(
            """
            () => {
              const toolbar = document.getElementById('customersSelectionToolbar');
              if (!toolbar) return;
              toolbar.classList.add('visible');
              toolbar.setAttribute('aria-hidden', 'false');
            }
            """
        )
        wait_for_visible(self.page, "#customersSelectionToolbar")

    def assert_selection_toolbar_surface(self) -> None:
        for selector in [
            "#customersSelectionToolbar",
            "#customersSelectionCount",
            "#customersDeactivateButton",
            "#customersReactivateButton",
        ]:
            wait_for_visible(self.page, selector)
