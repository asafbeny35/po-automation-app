from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.inventory_page import InventoryPage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_tab_core_controls_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("inventory")
    inventory = InventoryPage(page)
    inventory.assert_core_actions_visible()
    inventory.assert_sections_visible()
    inventory.assert_raw_inventory_surface()
    inventory.assert_finish_inventory_surface()
    inventory.assert_supplier_contacts_surface()
    inventory.assert_purchase_orders_surface()
    inventory.assert_supplier_delivery_surface()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_measure_calculator_toggles(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("inventory")
    inventory = InventoryPage(page)
    inventory.toggle_measure_calculator()
    inventory.assert_measure_calculator_surface()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_supplier_delivery_editor_surfaces_can_render(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("inventory")
    inventory = InventoryPage(page)
    inventory.open_supplier_delivery_editor_stub()
    inventory.assert_supplier_delivery_editor_surface()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_inventory_purchase_order_modals_can_render(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("inventory")
    inventory = InventoryPage(page)
    inventory.open_purchase_order_send_modal_stub()
    inventory.assert_purchase_order_send_modal_surfaces()
    inventory.open_purchase_order_delete_modal_stub()
    inventory.assert_purchase_order_delete_modal_surfaces()
