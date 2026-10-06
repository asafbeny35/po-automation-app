"""ביטול הזמנה מהיסטוריית ההזמנות.

אישור במודאל מבטל במורנינג את חשבונית המס ותעודת המשלוח (documents/{id}/close),
מסלק את ההזמנה מאישורי המסירה (כולל דיכוי) ומתשלומים והעברות — ומשאיר אותה
בהיסטוריה בלבד, מתויגת "ההזמנה בוטלה". אם שום מסמך לא בוטל בפועל — אין ניקוי,
כדי לא ליצור מצב שבו המסמכים חיים במורנינג אבל נעלמו מהמסכים.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import app


def _history_row(**overrides):
    row = {
        "history_id": "hist-cancel-1",
        "mode": "PROD",
        "customer_name": "כפיים בנייה",
        "po_number": "PO26001915",
        "fulfillment_id": "ful-1",
        "delivery_document_id": "doc-delivery-1",
        "delivery_document_number": "20430",
        "tax_invoice_document_id": "doc-invoice-1",
        "tax_invoice_number": "550700",
        "order_status_tag": "",
    }
    row.update(overrides)
    return row


class _FakeClient:
    def __init__(self, fail_ids=()):
        self.closed: list[str] = []
        self.fail_ids = set(fail_ids)

    async def _get_token(self):
        return "token"

    async def close_document(self, token, document_id):
        if document_id in self.fail_ids:
            raise RuntimeError(f"morning refused {document_id}")
        self.closed.append(document_id)
        return {"id": document_id, "status": 2, "number": 999}


def _patches(row, fake, saved, payments_matches=None):
    return (
        patch("app.load_order_history_rows", return_value=[row]),
        patch("app.get_mode_config", return_value={"base_url": "x", "api_key": "k", "api_secret": "s"}),
        patch("app.GreenInvoiceClient", return_value=fake),
        patch("app.add_delivery_confirmation_suppression") ,
        patch("app.delete_delivery_confirmation_rows", return_value={"status": "ok", "deleted": 1}),
        patch("app._matching_payment_rows_for_order_history_row", return_value=payments_matches or []),
        patch("app.delete_payment_transfer_row", return_value={"status": "ok"}),
        patch("app.save_order_history_rows", side_effect=lambda rows: saved.update(rows=[dict(r) for r in rows]) or {}),
    )


def test_missing_history_id_is_rejected(client):
    resp = client.post("/order-history-cancel-order", json={})
    assert resp.status_code == 400


def test_unknown_history_id_is_rejected(client):
    with patch("app.load_order_history_rows", return_value=[]):
        resp = client.post("/order-history-cancel-order", json={"history_id": "missing"})
    assert resp.status_code == 404


def test_an_already_cancelled_order_is_rejected(client):
    row = _history_row(order_status_tag="ההזמנה בוטלה")
    with patch("app.load_order_history_rows", return_value=[row]):
        resp = client.post("/order-history-cancel-order", json={"history_id": "hist-cancel-1"})
    assert resp.status_code == 400
    assert "כבר בוטלה" in resp.json()["error"]


def test_happy_path_cancels_both_documents_and_cleans_everything(client):
    row = _history_row()
    fake = _FakeClient()
    saved: dict = {}
    p = _patches(row, fake, saved)
    with p[0], p[1], p[2], p[3] as suppress_mock, p[4] as dc_mock, p[5], p[6], p[7]:
        resp = client.post("/order-history-cancel-order", json={"history_id": "hist-cancel-1"})
    assert resp.status_code == 200
    data = resp.json()
    # החשבונית מבוטלת לפני התעודה
    assert fake.closed == ["doc-invoice-1", "doc-delivery-1"]
    assert [m["status"] for m in data["morning"]] == ["cancelled", "cancelled"]
    suppress_mock.assert_called_once()
    dc_mock.assert_called_once()
    # השורה נשארה בהיסטוריה — מתויגת
    assert saved["rows"][0]["order_status_tag"] == "ההזמנה בוטלה"
    assert data["rows"][0]["order_status_tag"] == "ההזמנה בוטלה"


def test_payments_rows_are_deleted_in_cascade(client):
    row = _history_row()
    fake = _FakeClient()
    saved: dict = {}
    matches = [{"_sheet_title": "תשלומים והעברות 2026", "_sheet_row": 40}]
    p = _patches(row, fake, saved, payments_matches=matches)
    with p[0], p[1], p[2], p[3], p[4], p[5], p[6] as delete_payment_mock, p[7]:
        resp = client.post("/order-history-cancel-order", json={"history_id": "hist-cancel-1"})
    assert resp.status_code == 200
    delete_payment_mock.assert_called_once()
    assert delete_payment_mock.call_args.args[0] == "תשלומים והעברות 2026"
    assert delete_payment_mock.call_args.args[1] == 40


def test_total_morning_failure_aborts_without_any_cleanup(client):
    row = _history_row()
    fake = _FakeClient(fail_ids={"doc-invoice-1", "doc-delivery-1"})
    saved: dict = {}
    p = _patches(row, fake, saved)
    with p[0], p[1], p[2], p[3] as suppress_mock, p[4] as dc_mock, p[5], p[6], p[7] as save_mock:
        resp = client.post("/order-history-cancel-order", json={"history_id": "hist-cancel-1"})
    assert resp.status_code == 502
    suppress_mock.assert_not_called()
    dc_mock.assert_not_called()
    save_mock.assert_not_called()


def test_partial_morning_failure_still_cleans_up(client):
    """תעודה שנכשלה לא חוסמת: החשבונית בוטלה — ממשיכים ומדווחים על השגיאה."""
    row = _history_row()
    fake = _FakeClient(fail_ids={"doc-delivery-1"})
    saved: dict = {}
    p = _patches(row, fake, saved)
    with p[0], p[1], p[2], p[3], p[4] as dc_mock, p[5], p[6], p[7]:
        resp = client.post("/order-history-cancel-order", json={"history_id": "hist-cancel-1"})
    assert resp.status_code == 200
    statuses = {m["document"]: m["status"] for m in resp.json()["morning"]}
    assert statuses["חשבונית מס"] == "cancelled"
    assert statuses["תעודת משלוח"] == "error"
    dc_mock.assert_called_once()
    assert saved["rows"][0]["order_status_tag"] == "ההזמנה בוטלה"


def test_invoice_only_order_skips_the_missing_delivery(client):
    row = _history_row(delivery_document_id="", delivery_document_number="")
    fake = _FakeClient()
    saved: dict = {}
    p = _patches(row, fake, saved)
    with p[0], p[1], p[2], p[3], p[4], p[5], p[6], p[7]:
        resp = client.post("/order-history-cancel-order", json={"history_id": "hist-cancel-1"})
    assert resp.status_code == 200
    statuses = {m["document"]: m["status"] for m in resp.json()["morning"]}
    assert statuses["חשבונית מס"] == "cancelled"
    assert statuses["תעודת משלוח"] == "skipped"
    assert fake.closed == ["doc-invoice-1"]


def test_sandbox_row_uses_the_sandbox_config(client):
    row = _history_row(mode="SB")
    fake = _FakeClient()
    saved: dict = {}
    p = _patches(row, fake, saved)
    with p[0], p[1] as cfg_mock, p[2], p[3], p[4], p[5], p[6], p[7]:
        resp = client.post("/order-history-cancel-order", json={"history_id": "hist-cancel-1"})
    assert resp.status_code == 200
    cfg_mock.assert_called_once_with("sandbox")
