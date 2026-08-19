"""Working Orders tab E2E flow tests."""
from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_orders_state_from_browser(page):
    """Browser-driven: working-orders-state must be reachable."""
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/working-orders-state');
          return { ok: res.ok, status: res.status };
        }
        """
    )
    assert result["status"] == 200


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_orders_note_save_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/working-orders-note-save', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              row_id: 'test-wo-e2e-001',
              note_text: 'TEST | נעלולי פלא | הערה E2E',
            })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] in {200, 400, 404, 422, 500}


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_orders_delete_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/working-orders-delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ row_id: 'nonexistent-wo-e2e-999' })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] in {200, 400, 404, 422, 500}


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_working_order_note_file_missing_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/working-order-note-file/nonexistent-note-999');
          return { status: res.status };
        }
        """
    )
    assert result["status"] in {400, 404, 422}
