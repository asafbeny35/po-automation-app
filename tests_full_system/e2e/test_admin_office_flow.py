from __future__ import annotations

import pytest

from tests_full_system.page_objects.admin_page import AdminPage
from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.office_page import OfficePage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_admin_tab_core_controls_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("admin")
    admin = AdminPage(page)
    admin.assert_core_actions_visible()
    admin.assert_sections_visible()
    admin.assert_jump_navigation_visible()
    admin.assert_docs_surface()
    admin.assert_finance_refresh_controls()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_admin_business_doc_modal_can_render(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("admin")
    admin = AdminPage(page)
    admin.open_business_doc_send_modal_stub()
    admin.assert_business_doc_send_modal_surfaces()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_office_tab_core_controls_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("office")
    office = OfficePage(page)
    office.assert_core_actions_visible()
    office.assert_sections_visible()
    office.assert_vat_calculator_surface()
    office.assert_measure_calculator_surface()
