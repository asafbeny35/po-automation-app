from __future__ import annotations

import pytest

from tests_full_system.manifests.tabs import TOP_LEVEL_TABS
from tests_full_system.page_objects.app_shell import AppShell


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_dashboard_shell_loads(page):
    shell = AppShell(page)
    shell.open()
    assert page.locator(".top-tab").count() >= len(TOP_LEVEL_TABS)


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
@pytest.mark.parametrize("tab", TOP_LEVEL_TABS, ids=lambda item: item["label"])
def test_each_top_level_tab_exposes_its_key_surface(page, tab):
    shell = AppShell(page)
    shell.open()
    shell.open_tab(tab["tab_id"])
    shell.assert_tab_key_surface_visible(tab["tab_id"])
