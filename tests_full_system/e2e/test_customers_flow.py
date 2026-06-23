from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.customers_page import CustomersPage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_customers_tab_core_controls_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("customers")
    customers = CustomersPage(page)
    customers.assert_core_actions_visible()
    customers.assert_list_surface()
    customers.assert_create_form_surface()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_customers_archive_toggle_and_selection_toolbar_surfaces(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("customers")
    customers = CustomersPage(page)
    customers.toggle_inactive_archive()
    customers.assert_list_surface()
    customers.assert_inactive_list_surface()
    customers.show_selection_toolbar_stub()
    customers.assert_selection_toolbar_surface()
