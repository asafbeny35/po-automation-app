"""Bank integration E2E flow tests — Pazomat, Sibus, bank movements."""
from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_pazomat_state_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/pazomat-state');
          const data = await res.json().catch(() => null);
          return { status: res.status, isDict: typeof data === 'object' && data !== null && !Array.isArray(data) };
        }
        """
    )
    assert result["status"] == 200
    assert result["isDict"] is True


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_sibus_state_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/sibus-state');
          const data = await res.json().catch(() => null);
          return { status: res.status, isDict: typeof data === 'object' && data !== null && !Array.isArray(data) };
        }
        """
    )
    assert result["status"] == 200
    assert result["isDict"] is True


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_pazomat_refresh_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/pazomat-refresh', { method: 'POST' });
          return { status: res.status };
        }
        """
    )
    assert result["status"] < 500


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_sibus_refresh_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/sibus-refresh', { method: 'POST' });
          return { status: res.status };
        }
        """
    )
    assert result["status"] < 500


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_sibus_monthly_check_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/sibus-monthly-check', { method: 'POST' });
          return { status: res.status };
        }
        """
    )
    assert result["status"] < 500
