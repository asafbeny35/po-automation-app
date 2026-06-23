from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_tab_does_not_throw_known_runtime_errors_on_open(page):
    page_errors: list[str] = []
    page.on("pageerror", lambda exc: page_errors.append(str(exc)))

    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")

    page.wait_for_timeout(750)

    assert not any("financeInvoiceSortDateValue is not defined" in error for error in page_errors), page_errors
