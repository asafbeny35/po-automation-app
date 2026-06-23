from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.payments_page import PaymentsPage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_payments_tab_core_controls_exist(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("payments-transfers")
    payments = PaymentsPage(page)
    payments.assert_core_actions_visible()
    payments.assert_jump_cards_visible()
    payments.assert_search_surface()
    payments.assert_collection_and_payment_sections()
    payments.assert_filter_buttons_present()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_payments_inline_editor_surface_can_render(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("payments-transfers")
    payments = PaymentsPage(page)
    payments.open_inline_editor_stub()
    payments.assert_inline_editor_surface()
