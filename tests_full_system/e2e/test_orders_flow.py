from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.orders_page import OrdersPage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_orders_tab_core_controls_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.open_manual_entry()
    orders.assert_core_actions_visible()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_partial_delivery_confirmation_appears_when_quantity_not_changed(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.fill_minimal_manual_order(quantity="1")
    orders.load_manual_order_to_screen()
    orders.toggle_partial_delivery()
    page.locator('button[onclick="send(\'sandbox\')"]').click()
    orders.assert_partial_delivery_confirmation_modal()
