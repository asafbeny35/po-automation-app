from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.marketing_page import MarketingPage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_marketing_tab_core_controls_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("marketing")
    marketing = MarketingPage(page)
    marketing.assert_core_actions_visible()
    marketing.assert_sections_visible()
    marketing.assert_pipeline_surface()
    marketing.assert_work_managers_surface()
    marketing.assert_construction_companies_surface()
    marketing.assert_reminders_surface()
    marketing.assert_history_and_docs_surface()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_marketing_pipeline_toggle_and_modal_surfaces(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("marketing")
    marketing = MarketingPage(page)
    marketing.toggle_pipeline()
    marketing.assert_pipeline_surface()
    marketing.open_mail_modal_stub()
    marketing.assert_mail_modal_surface()
    marketing.open_doc_whatsapp_modal_stub()
    marketing.assert_doc_whatsapp_modal_surface()
    marketing.open_comm_modal_stub()
    marketing.assert_comm_modal_surface()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_marketing_reminder_and_bulk_send_modals_can_render(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("marketing")
    marketing = MarketingPage(page)
    marketing.open_reminder_modal_stub()
    marketing.assert_reminder_modal_surface()
    marketing.open_work_managers_send_modal_stub()
    marketing.assert_work_managers_send_modal_surface()
    marketing.open_construction_companies_send_modal_stub()
    marketing.assert_construction_companies_send_modal_surface()
