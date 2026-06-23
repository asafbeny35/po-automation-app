from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_support_center_opens_and_closes(page):
    shell = AppShell(page)
    shell.open()
    shell.open_support_center()
    shell.close_support_center()
