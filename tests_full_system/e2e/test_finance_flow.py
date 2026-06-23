from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.finance_page import FinancePage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_tab_core_controls_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    finance = FinancePage(page)
    finance.assert_core_actions_visible()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_send_modal_opens(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    finance = FinancePage(page)
    finance.open_send_invoices_modal()
