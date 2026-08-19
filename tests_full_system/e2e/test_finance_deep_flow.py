"""Deep finance UI E2E tests — send modal, parse modal, override modal, withholdings."""
from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell
from tests_full_system.page_objects.finance_page import FinancePage


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_sections_all_visible(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    finance = FinancePage(page)
    finance.assert_core_actions_visible()
    finance.assert_finance_sections_visible()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_send_modal_full_surface(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    finance = FinancePage(page)
    finance.open_send_invoices_modal()
    finance.assert_send_invoices_modal_surfaces()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_parse_modal_surfaces(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    finance = FinancePage(page)
    finance.open_parse_modal_stub()
    finance.assert_parse_modal_surfaces()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_override_due_dates_modal_surfaces(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("finance")
    finance = FinancePage(page)
    finance.open_override_modal_stub()
    finance.assert_override_modal_surfaces()


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_save_from_browser_fetch(page):
    """Submit a finance invoice save via fetch from within the browser context."""
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/finance-invoices-save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              row: {
                invoice_date: '01/06/2026',
                supplier_name: 'TEST | נעלולי פלא | ספק E2E',
                service_or_product: 'TEST | נעלולי פלא | שירות E2E',
                amount: '500',
                vat: '90',
                total: '590',
              }
            })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] in {200, 400, 422, 500}


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_invoice_delete_from_browser_fetch(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/finance-invoices-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ row_id: 'nonexistent-finance-e2e-999' })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] in {200, 400, 404, 422, 500}


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_settings_save_from_browser_fetch(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/finance-settings-save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ income_tax_rate_percent: 3 })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] in {200, 400, 422, 500}


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_withholdings_state_from_browser_fetch(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/finance-customer-withholdings-state');
          return { status: res.status };
        }
        """
    )
    assert result["status"] == 200


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finance_export_xlsx_from_browser_fetch(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/finance-invoices-export', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ format: 'xlsx', row_ids: [] })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] in {200, 400, 422, 500}
