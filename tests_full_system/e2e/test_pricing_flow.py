from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.pricing_page import PricingPage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_pricing_tab_core_controls_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("pricing-bom")
    pricing = PricingPage(page)
    pricing.assert_core_actions_visible()
    pricing.assert_pricing_surface()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_pricing_editor_surface_can_render(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("pricing-bom")
    pricing = PricingPage(page)
    pricing.open_editor_stub()
    pricing.assert_editor_surface()
