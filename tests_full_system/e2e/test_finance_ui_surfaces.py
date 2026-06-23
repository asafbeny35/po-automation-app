from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.finance_page import FinancePage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_sections_and_controls_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    finance = FinancePage(page)
    finance.assert_core_actions_visible()
    finance.assert_finance_sections_visible()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_send_modal_has_expected_controls(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    finance = FinancePage(page)
    finance.open_send_invoices_modal()
    finance.assert_send_invoices_modal_surfaces()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_override_modal_surface_can_render(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    finance = FinancePage(page)
    finance.open_override_modal_stub()
    finance.assert_override_modal_surfaces()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_parse_modal_surface_can_render(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    finance = FinancePage(page)
    finance.open_parse_modal_stub()
    finance.assert_parse_modal_surfaces()
