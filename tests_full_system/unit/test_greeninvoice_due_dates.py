from datetime import date
from types import SimpleNamespace

import pytest

from services.greeninvoice import GreenInvoiceClient
from services.models import POItem, PurchaseOrderData
from services.payment_terms import calculate_net_due_date


@pytest.mark.unit
@pytest.mark.parametrize(
    ("issue_date", "terms_days", "expected"),
    [
        (date(2026, 6, 21), 0, date(2026, 7, 1)),
        (date(2026, 5, 27), 60, date(2026, 8, 1)),
        (date(2026, 4, 29), 60, date(2026, 7, 1)),
        (date(2026, 3, 10), 120, date(2026, 8, 1)),
        (date(2026, 12, 31), -30, date(2027, 1, 1)),
    ],
)
def test_calculate_net_due_date_matches_payment_screen(issue_date, terms_days, expected) -> None:
    assert calculate_net_due_date(issue_date, terms_days) == expected


@pytest.mark.unit
@pytest.mark.asyncio
async def test_sales_document_context_builds_explicit_document_and_due_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    client = GreenInvoiceClient("https://example.test/api/v1", "key", "secret")
    po = PurchaseOrderData(
        po_number="PO-1",
        customer_name="לקוח בדיקה",
        customer_id="515151515",
        payment_terms_days=60,
    )

    async def fake_token() -> str:
        return "token"

    async def fake_delivery_type(_token: str) -> int:
        return 200

    async def fake_customer(_token: str, _value: str):
        return {"id": "customer-id"}

    monkeypatch.setattr(client, "_get_token", fake_token)
    monkeypatch.setattr(client, "_resolve_delivery_type", fake_delivery_type)
    monkeypatch.setattr(client, "_find_customer_by_id", fake_customer)
    monkeypatch.setattr("services.greeninvoice.business_today", lambda: date(2026, 5, 27))

    ctx = await client._build_sales_document_context(po)

    assert ctx["document_date"] == "2026-05-27"
    assert ctx["due_date"] == "2026-08-01"


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("creation_method", ["create_delivery_only", "create_invoice_only", "create_delivery_and_invoice"])
async def test_every_sales_document_creation_path_sends_due_date(
    creation_method: str,
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = GreenInvoiceClient("https://example.test/api/v1", "key", "secret")
    po = PurchaseOrderData(
        po_number="PO-2",
        customer_name="לקוח בדיקה",
        payment_terms_days=30,
        items=[POItem(description="מוצר", quantity=1, unit_price=100, line_total=100)],
    )
    captured_payloads: list[dict] = []

    async def fake_context(_po: PurchaseOrderData) -> dict:
        return {
            "token": "token",
            "delivery_type": 200,
            "invoice_type": 305,
            "footer_text": "footer",
            "client_payload": {"id": "customer-id"},
            "folder_name": "folder",
            "document_date": "2026-08-19",
            "due_date": "2026-10-01",
        }

    async def fake_create_document(_token: str, payload: dict):
        captured_payloads.append(payload)
        return SimpleNamespace(
            document_id=f"doc-{len(captured_payloads)}",
            number=str(550000 + len(captured_payloads)),
            url="",
        )

    monkeypatch.setattr(client, "_build_sales_document_context", fake_context)
    monkeypatch.setattr(client, "create_document", fake_create_document)

    await getattr(client, creation_method)(po, output_dir=tmp_path)

    assert captured_payloads
    assert all(payload["date"] == "2026-08-19" for payload in captured_payloads)
    assert all(payload["dueDate"] == "2026-10-01" for payload in captured_payloads)
