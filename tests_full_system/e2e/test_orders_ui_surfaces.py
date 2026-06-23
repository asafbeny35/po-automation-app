from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.orders_page import OrdersPage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_orders_manual_fields_and_actions_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.open_manual_entry()
    orders.assert_manual_fields_visible()
    orders.assert_creation_buttons_grouped()
    orders.assert_progress_bar_present()
    orders.assert_history_widgets_visible()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_orders_quote_mode_switch_changes_surface(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.switch_to_quote_mode()
    assert "הצעת מחיר" in page.locator("#manualEntryHeading").inner_text()
    assert page.locator("#manualPartialDeliveryWrap").is_hidden()
    orders.switch_to_order_mode()
    assert "הזמנה" in page.locator("#manualEntryHeading").inner_text()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_orders_label_split_modal_opens(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.open_label_split_modal()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_orders_history_panels_can_open(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.open_order_history_panel()
    orders.assert_order_history_panel_surfaces()
    orders.open_quote_history_panel()
    orders.assert_quote_history_panel_surfaces()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_order_history_delete_modal_surface_can_render(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("orders")
    orders = OrdersPage(page)
    orders.open_order_history_delete_modal_stub()
    orders.assert_order_history_delete_modal_surface()
