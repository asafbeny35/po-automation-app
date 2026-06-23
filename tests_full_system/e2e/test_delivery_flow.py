from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.delivery_page import DeliveryPage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_tab_core_controls_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    delivery = DeliveryPage(page)
    delivery.assert_core_actions_visible()
    delivery.assert_upload_surface()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_delivery_rows_and_contacts_actions_can_render(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    delivery = DeliveryPage(page)
    delivery.seed_delivery_rows_stub()
    delivery.seed_delivery_contacts_stub()
