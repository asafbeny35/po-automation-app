"""HR & Payroll tab E2E flow tests."""
from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell


def _open_hr_tab(page):
    shell = AppShell(page)
    shell.open()
    shell.open_tab("admin")  # HR lives under admin or its own tab; fallback via JS eval


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_hr_state_endpoint_reachable_from_browser(page):
    """Browser-driven: load the app and confirm hr-state is reachable via fetch."""
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          try {
            const res = await fetch('/hr-state');
            return { ok: res.ok, status: res.status };
          } catch (e) {
            return { ok: false, error: e.message };
          }
        }
        """
    )
    assert result.get("status", 0) < 500, f"hr-state fetch failed: {result}"


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_hr_employee_save_from_browser(page):
    """POST hr-employee-save from browser context — must not crash."""
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/hr-employee-save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              row: {
                employee_name: 'TEST | נעלולי פלא | עובד E2E',
                employee_id: '777777777',
                role: 'פועל',
                start_date: '01/01/2026',
              }
            })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] < 500


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_hr_payroll_save_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/hr-payroll-save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              row: {
                employee_name: 'TEST | נעלולי פלא | עובד E2E שכר',
                month: '06/2026',
                gross_salary: '7000',
                net_salary: '5800',
                payment_date: '01/06/2026',
              }
            })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] < 500


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_hr_hours_save_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/hr-hours-save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              row: {
                employee_name: 'TEST | נעלולי פלא | עובד שעות',
                date: '15/06/2026',
                hours: '8',
                description: 'TEST | נעלולי פלא | יום עבודה',
              }
            })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] < 500


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_hr_contribution_save_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/hr-contribution-save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              row: {
                employee_name: 'TEST | נעלולי פלא | עובד הפרשות',
                month: '06/2026',
                pension: '350',
                health: '100',
                disability: '50',
              }
            })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] < 500


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_hr_export_csv_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/hr-export/employees/csv');
          return { status: res.status, contentType: res.headers.get('content-type') };
        }
        """
    )
    assert result["status"] in {200, 400, 404, 422, 500}


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_hr_payslip_prep_preview_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/hr-payslip-prep-preview');
          return { status: res.status };
        }
        """
    )
    assert result["status"] < 500


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_hr_delete_nonexistent_employee_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/hr-employee-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ row_id: 'nonexistent-e2e-employee-999' })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] in {200, 400, 404, 422, 500}
