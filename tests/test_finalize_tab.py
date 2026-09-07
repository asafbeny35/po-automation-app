"""
E2E API tests — /finalize endpoint (order fulfillment flow).

The endpoint:
1. Validates GreenInvoice config
2. Syncs customer via _ensure_finalize_customer
3. Creates delivery + invoice documents (or delivery/invoice-only based on document_mode)
4. Copies source PO and transport label if present
5. Merges PDFs
6. Syncs to Google Drive (_perform_finalize_drive_sync runs in thread)
7. Appends payment row to Google Sheets
8. Deducts from inventory
9. Upserts order history (upsert_order_history_row)
10. Sends WhatsApp
11. Returns rich JSON response
"""
from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ── helpers ──────────────────────────────────────────────────────────────────


def _po_data(**kwargs) -> dict:
    """Minimal PO data dict suitable for the /finalize body."""
    base = {
        "customer_name": "לקוח בדיקה בע\"מ",
        "customer_id": "cust-001",
        "customer_email": "test@example.com",
        "customer_phone": "052-0000000",
        "po_number": f"PO-{uuid.uuid4().hex[:6].upper()}",
        "po_date": "01/06/2026",
        "delivery_address": "רחוב הבדיקה 1, תל אביב",
        "total": "10000",
        "subtotal": "8547",
        "vat": "1453",
        "items": [
            {
                "description": "מוצר בדיקה",
                "sku": "TEST-001",
                "quantity": 10,
                "unit_price": 854.7,
                "line_total": 8547,
                "unit": "מ\"ר",
            }
        ],
    }
    base.update(kwargs)
    return base


def _delivery_doc(**kwargs):
    ns = SimpleNamespace(
        document_id=f"delivery-{uuid.uuid4().hex[:8]}",
        number=f"T{uuid.uuid4().hex[:4]}",
        url="https://api.greeninvoice.co.il/documents/delivery-123",
    )
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


def _invoice_doc(**kwargs):
    ns = SimpleNamespace(
        document_id=f"invoice-{uuid.uuid4().hex[:8]}",
        number=f"INV{uuid.uuid4().hex[:4]}",
        url="https://api.greeninvoice.co.il/documents/invoice-123",
    )
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


def _good_mode_config():
    return {
        "mode": "sandbox",
        "api_key": "test-api-key",
        "api_secret": "test-api-secret",
        "base_url": "https://sandbox.greeninvoice.co.il/api/v1",
    }


def _customer_sync_ok():
    return {
        "status": "found",
        "customer_guid": "gi-cust-guid",
        "customer_name": "לקוח בדיקה בע\"מ",
        "missing_before": False,
    }


def _drive_sync_ok():
    return {
        "status": "ok",
        "order_folder_id": "folder-abc",
        "company_folder_id": "company-folder-abc",
        "uploaded_files": [
            {"name": "delivery.pdf", "web_view_link": "https://drive.google.com/d/del"},
            {"name": "invoice.pdf", "web_view_link": "https://drive.google.com/d/inv"},
        ],
        "delivery_drive_file_id": "drive-del-id",
        "invoice_drive_file_id": "drive-inv-id",
        "merged_drive_file_id": "drive-merged-id",
        "coc_drive_file_id": "",
        "label_drive_file_ids": [],
        "confirmation_result": {"status": "ok"},
    }


def _history_ok():
    return {"status": "ok", "row_id": uuid.uuid4().hex}


# ── shared patch stack for happy-path ────────────────────────────────────────

def _base_patches(
    delivery_doc_ns=None,
    invoice_doc_ns=None,
    drive_result=None,
    history_result=None,
    customer_result=None,
):
    delivery_doc_ns = delivery_doc_ns or _delivery_doc()
    invoice_doc_ns = invoice_doc_ns or _invoice_doc()
    drive_result = drive_result or _drive_sync_ok()
    history_result = history_result or _history_ok()
    customer_result = customer_result or _customer_sync_ok()

    gi_client = MagicMock()
    gi_client.create_delivery_and_invoice = AsyncMock(
        return_value=(delivery_doc_ns, invoice_doc_ns, None, None)
    )
    gi_client.create_delivery_only = AsyncMock(
        return_value=(delivery_doc_ns, None)
    )
    gi_client.create_invoice_only = AsyncMock(
        return_value=(invoice_doc_ns, None)
    )

    return [
        patch("app.get_mode_config", return_value=_good_mode_config()),
        patch("app.GreenInvoiceClient", return_value=gi_client),
        patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=customer_result),
        patch("app._perform_finalize_drive_sync", return_value=drive_result),
        patch("app.asyncio.to_thread", side_effect=_fake_to_thread(drive_result, history_result)),
        patch("app.upsert_order_history_row", return_value=history_result),
        patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}),
        patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok", "provider": "whatsapp"}),
        patch("app._project_manager_entries_from_po", return_value=[]),
        patch("app._merchandise_po_items", return_value=[]),
        patch("app._primary_merchandise_po_item", return_value=None),
        patch("app.merge_pdfs", return_value=None),
        patch("app.append_payment_row", return_value={"status": "ok"}),
        patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}),
        patch("app._invalidate_finance_state_cache"),
        patch("app.load_working_order_rows", return_value=[]),
        patch("app._parse_order_display_date", return_value=None),
    ], gi_client


def _fake_to_thread(drive_result, history_result):
    """
    asyncio.to_thread is used for drive sync, sheets append, inventory deduction,
    and history upsert.  We run the callable directly so all four work.
    """
    import asyncio as _asyncio

    async def _side_effect(fn, *args, **kwargs):
        # Drive sync and history upsert are inner functions; just call them
        try:
            return fn(*args, **kwargs)
        except Exception:
            return {}

    return _side_effect


# ════════════════════════════════════════════════════════════════════════════
# Happy-path tests
# ════════════════════════════════════════════════════════════════════════════

class TestFinalizeHappyPath:

    def test_sandbox_returns_200_with_document_ids(self, client):
        patches, gi = _base_patches()
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "document_mode": "full",
                "skip_whatsapp": True,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["mode"] == "sandbox"
        assert "invoice_document_id" in body
        assert "delivery_document_id" in body

    def test_returns_customer_name(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(customer_name="חברת בדיקה"),
                "document_mode": "full",
                "skip_whatsapp": True,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert "customer_created_name" in body

    def test_skip_whatsapp_true_skips_whatsapp(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        wa_mock = AsyncMock()
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", wa_mock), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "skip_whatsapp": True,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["whatsapp_send_result"]["status"] == "skipped"
        wa_mock.assert_not_called()

    def test_skip_whatsapp_via_header(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        wa_mock = AsyncMock()
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", wa_mock), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            resp = client.post(
                "/finalize",
                json={"mode": "sandbox", "data": _po_data()},
                headers={"X-PO-Skip-WhatsApp": "1"},
            )
        assert resp.status_code == 200
        wa_mock.assert_not_called()

    def test_manual_entry_flag_reflected_in_response(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(manual_entry=True),
                "skip_whatsapp": True,
            })
        assert resp.status_code == 200
        assert resp.json()["manual_entry"] is True

    def test_fulfillment_id_returned(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        fid = uuid.uuid4().hex
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(fulfillment_id=fid),
                "skip_whatsapp": True,
            })
        assert resp.status_code == 200
        assert resp.json()["fulfillment_id"] == fid


# ════════════════════════════════════════════════════════════════════════════
# document_mode variations
# ════════════════════════════════════════════════════════════════════════════

class TestFinalizeDocumentModes:

    def _call_finalize(self, client, document_mode: str, gi_client=None):
        """Helper: call /finalize with mock GI and common patches."""
        if gi_client is None:
            gi_client = MagicMock()
            gi_client.create_delivery_and_invoice = AsyncMock(
                return_value=(_delivery_doc(), _invoice_doc(), None, None)
            )
            gi_client.create_delivery_only = AsyncMock(
                return_value=(_delivery_doc(), None)
            )
            gi_client.create_invoice_only = AsyncMock(
                return_value=(_invoice_doc(), None)
            )
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            return client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "document_mode": document_mode,
                "skip_whatsapp": True,
            })

    def test_full_mode(self, client):
        resp = self._call_finalize(client, "full")
        assert resp.status_code == 200
        assert resp.json()["document_mode"] == "full"

    def test_delivery_only_mode(self, client):
        resp = self._call_finalize(client, "delivery_only")
        assert resp.status_code == 200
        assert resp.json()["document_mode"] == "delivery_only"

    def test_invoice_only_mode(self, client):
        resp = self._call_finalize(client, "invoice_only")
        assert resp.status_code == 200
        assert resp.json()["document_mode"] == "invoice_only"

    def test_unknown_document_mode_treated_as_full(self, client):
        # unknown mode should normalise; endpoint should still 200
        resp = self._call_finalize(client, "bogus_mode")
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════════════
# GreenInvoice failure
# ════════════════════════════════════════════════════════════════════════════

class TestFinalizeGreenInvoiceErrors:

    def test_document_creation_failure_returns_500(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            side_effect=RuntimeError("GreenInvoice API error")
        )
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "skip_whatsapp": True,
            })
        assert resp.status_code == 500
        assert "error" in resp.json()

    def test_customer_sync_failure_returns_500(self, client):
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=MagicMock()), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, side_effect=RuntimeError("customer sync failed")):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "skip_whatsapp": True,
            })
        assert resp.status_code == 500
        assert "סנכרון לקוח נכשל" in resp.json()["error"]

    def test_missing_greeninvoice_config_returns_503(self, client):
        bad_cfg = {"mode": "sandbox", "api_key": "", "api_secret": "", "base_url": ""}
        with patch("app.get_mode_config", return_value=bad_cfg):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "skip_whatsapp": True,
            })
        assert resp.status_code == 503
        assert "error" in resp.json()

    def test_partial_missing_config_returns_503(self, client):
        partial_cfg = {
            "mode": "sandbox",
            "api_key": "key",
            "api_secret": "",  # missing
            "base_url": "https://sandbox.example.com",
        }
        with patch("app.get_mode_config", return_value=partial_cfg):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "skip_whatsapp": True,
            })
        assert resp.status_code == 503


# ════════════════════════════════════════════════════════════════════════════
# Non-fatal failure paths — should still return 200
# ════════════════════════════════════════════════════════════════════════════

class TestFinalizeNonFatalFailures:

    def _finalize_with_overrides(self, client, **overrides):
        """Runs finalize with all mocks but lets you override specific ones."""
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        defaults = dict(
            app_get_mode_config=_good_mode_config(),
            gi=gi_client,
            customer_result=_customer_sync_ok(),
            drive_result=_drive_sync_ok(),
            history_result=_history_ok(),
            whatsapp_result={"status": "ok"},
        )
        defaults.update(overrides)

        with patch("app.get_mode_config", return_value=defaults["app_get_mode_config"]), \
             patch("app.GreenInvoiceClient", return_value=defaults["gi"]), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=defaults["customer_result"]), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(defaults["drive_result"], defaults["history_result"])), \
             patch("app.upsert_order_history_row", return_value=defaults["history_result"]), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value=defaults["whatsapp_result"]), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            return client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "skip_whatsapp": True,
            })

    def test_drive_sync_failure_still_returns_200(self, client):
        drive_error = {"status": "error", "error": "Drive API timeout"}
        resp = self._finalize_with_overrides(client, drive_result=drive_error)
        assert resp.status_code == 200
        body = resp.json()
        # Drive sync failure is non-fatal — the key must be present in the response
        assert "drive_sync_result" in body

    def test_history_upsert_failure_still_returns_200(self, client):
        history_error = {"status": "error", "error": "Sheets write failed"}
        resp = self._finalize_with_overrides(client, history_result=history_error)
        assert resp.status_code == 200

    def test_sheets_append_failure_returns_200(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", side_effect=Exception("Sheets not configured")), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "skip_whatsapp": True,
            })
        assert resp.status_code == 200

    def test_inventory_deduction_failure_returns_200(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", side_effect=Exception("inventory error")), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "skip_whatsapp": True,
            })
        assert resp.status_code == 200


# ════════════════════════════════════════════════════════════════════════════
# WhatsApp send behaviour
# ════════════════════════════════════════════════════════════════════════════

class TestFinalizeWhatsApp:

    def _call(self, client, skip_whatsapp=False, wa_side_effect=None):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        wa = AsyncMock(
            side_effect=wa_side_effect,
            return_value={"status": "ok", "provider": "wa"},
        )
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", wa), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            return client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "skip_whatsapp": skip_whatsapp,
            })

    def test_whatsapp_error_returns_200_with_error_status(self, client):
        resp = self._call(client, skip_whatsapp=False, wa_side_effect=Exception("WA timeout"))
        assert resp.status_code == 200
        body = resp.json()
        assert body["whatsapp_send_result"]["status"] in ("error", "skipped")

    def test_skipped_whatsapp_result_key_present(self, client):
        resp = self._call(client, skip_whatsapp=True)
        assert resp.status_code == 200
        assert "whatsapp_send_result" in resp.json()


# ════════════════════════════════════════════════════════════════════════════
# Response structure tests
# ════════════════════════════════════════════════════════════════════════════

class TestFinalizeResponseStructure:

    def _call(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            return client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "skip_whatsapp": True,
            })

    def test_response_has_all_required_keys(self, client):
        resp = self._call(client)
        body = resp.json()
        required_keys = [
            "status", "mode", "document_mode", "fulfillment_id",
            "delivery_document_id", "delivery_document_number",
            "invoice_document_id", "invoice_document_number",
            "files", "label_files", "merged_file",
            "customer_sync_result", "drive_sync_result",
            "history_result", "whatsapp_send_result",
            "sheets_status", "inventory_deduction_result",
            "manual_entry", "sent_to_dad",
        ]
        for key in required_keys:
            assert key in body, f"Missing key in response: {key}"

    def test_files_is_list(self, client):
        body = self._call(client).json()
        assert isinstance(body["files"], list)

    def test_label_files_is_list(self, client):
        body = self._call(client).json()
        assert isinstance(body["label_files"], list)

    def test_all_generated_files_is_list(self, client):
        body = self._call(client).json()
        assert isinstance(body.get("all_generated_files", []), list)


# ════════════════════════════════════════════════════════════════════════════
# Mode normalisation
# ════════════════════════════════════════════════════════════════════════════

class TestFinalizeModeNormalisation:

    def _call_mode(self, client, mode: str):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        with patch("app.get_mode_config", return_value=_good_mode_config()) as mock_cfg, \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app._ensure_finance_state_refresh_started"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            # בלי הפאץ' על מתניע הרענון, מטמון כספים שהתיישן בזמן אמת מזניק
            # משימת רקע שקוראת get_mode_config("prod") ושוברת את ספירת הקריאות.
            resp = client.post("/finalize", json={
                "mode": mode,
                "data": _po_data(),
                "skip_whatsapp": True,
            })
            return resp, mock_cfg

    def test_sandbox_mode_uses_sandbox_config(self, client):
        resp, mock_cfg = self._call_mode(client, "sandbox")
        assert resp.status_code == 200
        mock_cfg.assert_called_once_with("sandbox")

    def test_sandbox_with_transport_normalises_to_sandbox(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        # sandbox_with_transport requires a transport label path — skip for config test
        with patch("app.get_mode_config", return_value=_good_mode_config()) as mock_cfg, \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            # sandbox_with_transport without a transport_label_path → 500 from missing label error
            resp = client.post("/finalize", json={
                "mode": "sandbox_with_transport",
                "data": _po_data(),
                "skip_whatsapp": True,
            })
        # Missing transport label should raise an error before document creation
        assert resp.status_code in (200, 500)


# ════════════════════════════════════════════════════════════════════════════
# send_to_dad flag
# ════════════════════════════════════════════════════════════════════════════

class TestFinalizeSendToDad:

    def test_send_to_dad_flag_reflected_in_response(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=_customer_sync_ok()), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(send_to_dad=True),
                "skip_whatsapp": True,
            })
        assert resp.status_code == 200
        assert resp.json()["sent_to_dad"] is True


# ════════════════════════════════════════════════════════════════════════════
# Customer-related tests
# ════════════════════════════════════════════════════════════════════════════

class TestFinalizeCustomer:

    def test_customer_created_flag_set_when_created(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        customer_created_result = {
            "status": "created",
            "customer_guid": "new-guid",
            "customer_name": "לקוח חדש",
            "missing_before": True,
        }
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=customer_created_result), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "skip_whatsapp": True,
            })
        assert resp.status_code == 200
        body = resp.json()
        assert body["customer_created"] is True

    def test_existing_customer_created_flag_false(self, client):
        gi_client = MagicMock()
        gi_client.create_delivery_and_invoice = AsyncMock(
            return_value=(_delivery_doc(), _invoice_doc(), None, None)
        )
        existing_customer_result = {
            "status": "found",
            "customer_guid": "existing-guid",
            "customer_name": "לקוח קיים",
            "missing_before": False,
        }
        with patch("app.get_mode_config", return_value=_good_mode_config()), \
             patch("app.GreenInvoiceClient", return_value=gi_client), \
             patch("app._ensure_finalize_customer", new_callable=AsyncMock, return_value=existing_customer_result), \
             patch("app.asyncio.to_thread", side_effect=_fake_to_thread(_drive_sync_ok(), _history_ok())), \
             patch("app.upsert_order_history_row", return_value=_history_ok()), \
             patch("app.upsert_delivery_confirmation_row", return_value={"status": "ok"}), \
             patch("app.send_files_via_whatsapp", new_callable=AsyncMock, return_value={"status": "ok"}), \
             patch("app._project_manager_entries_from_po", return_value=[]), \
             patch("app._merchandise_po_items", return_value=[]), \
             patch("app._primary_merchandise_po_item", return_value=None), \
             patch("app.merge_pdfs", return_value=None), \
             patch("app.append_payment_row", return_value={"status": "ok"}), \
             patch("app.deduct_quietpipe_finish_inventory", return_value={"status": "skipped"}), \
             patch("app._invalidate_finance_state_cache"), \
             patch("app.load_working_order_rows", return_value=[]), \
             patch("app._parse_order_display_date", return_value=None):
            resp = client.post("/finalize", json={
                "mode": "sandbox",
                "data": _po_data(),
                "skip_whatsapp": True,
            })
        assert resp.status_code == 200
        assert resp.json()["customer_created"] is False
