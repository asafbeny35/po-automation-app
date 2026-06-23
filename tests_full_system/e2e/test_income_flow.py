from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.income_page import IncomePage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_income_tab_core_controls_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("income")
    income = IncomePage(page)
    income.assert_core_actions_visible()
    income.assert_receipts_surface()
    income.assert_income_overview_surface()
