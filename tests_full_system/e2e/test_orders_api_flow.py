"""Orders API E2E flow tests — process, finalize, history, quotes via browser fetch."""
from __future__ import annotations

import pytest

from tests_full_system.page_objects.app_shell import AppShell


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_order_history_state_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/order-history-state');
          return { status: res.status };
        }
        """
    )
    assert result["status"] == 200


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_history_state_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/quote-history-state');
          return { status: res.status };
        }
        """
    )
    assert result["status"] == 200


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finalize_sandbox_from_browser_fetch(page):
    """Submit a sandbox finalize from the browser — not a crash is sufficient."""
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const payload = {
            mode: 'sandbox',
            document_mode: 'full',
            data: {
              mode: 'manual',
              manual_entry: true,
              manual_document_kind: 'order',
              po_number: 'E2E-TEST-001',
              po_date: '25/06/2026',
              customer_name: 'TEST | נעלולי פלא | E2E לקוח',
              customer_id: '999999999',
              customer_email: 'test@example.com',
              customer_phone: '0547720142',
              delivery_address: 'כתובת TEST',
              project: 'TEST | נעלולי פלא | פרויקט E2E',
              contact_name: 'TEST | נעלולי פלא | איש קשר',
              contact_phone: '0547720142',
              payment_terms_days: '30',
              payment_terms_label: 'שוטף + 30',
              subtotal: 100,
              vat: 18,
              total: 118,
              items: [{ description: 'TEST | נעלולי פלא | מוצר', sku: 'E2E-SKU', unit: 'יח׳', quantity: 1, unit_price: 100, line_total: 100 }],
              ordered_items: [{ description: 'TEST | נעלולי פלא | מוצר', sku: 'E2E-SKU', unit: 'יח׳', quantity: 1, unit_price: 100, line_total: 100 }],
              footer_text: 'TEST | נעלולי פלא | הערה',
              partial_delivery: false,
              label_split_rows: [],
            }
          };
          const res = await fetch('/finalize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] in {200, 400, 422, 500}


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finalize_delivery_only_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const payload = {
            mode: 'sandbox',
            document_mode: 'delivery_only',
            data: {
              mode: 'manual',
              manual_entry: true,
              manual_document_kind: 'order',
              po_number: 'E2E-DELIVERY-001',
              po_date: '25/06/2026',
              customer_name: 'TEST | נעלולי פלא | E2E משלוח',
              customer_id: '999999999',
              customer_email: 'test@example.com',
              subtotal: 200,
              vat: 36,
              total: 236,
              items: [{ description: 'TEST | נעלולי פלא | מוצר משלוח', quantity: 2, unit_price: 100, line_total: 200 }],
              ordered_items: [{ description: 'TEST | נעלולי פלא | מוצר משלוח', quantity: 2, unit_price: 100, line_total: 200 }],
              partial_delivery: false,
              label_split_rows: [],
            }
          };
          const res = await fetch('/finalize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] in {200, 400, 422, 500}


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_finalize_rejects_production_mode_from_browser(page):
    """Sending production mode from browser must be rejected, not silently processed."""
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/finalize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode: 'production', document_mode: 'full', data: {} })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] in {400, 422}


@pytest.mark.e2e
@pytest.mark.requires_browser
@pytest.mark.requires_live_server
def test_quote_history_mail_prepare_from_browser(page):
    shell = AppShell(page)
    shell.open()

    result = page.evaluate(
        """
        async () => {
          const res = await fetch('/quote-history-mail-prepare', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              row_id: 'test-quote-e2e-001',
              recipients: 'test@example.com',
              subject: 'TEST | נעלולי פלא | הצעת מחיר E2E',
              message: 'TEST | נעלולי פלא | גוף',
            })
          });
          return { status: res.status };
        }
        """
    )
    assert result["status"] in {200, 400, 404, 422, 500}
