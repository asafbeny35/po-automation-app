from pathlib import Path

import app
import pytest


def test_try_sync_source_po_to_drive_for_process(monkeypatch, tmp_path):
    source_path = tmp_path / "source.pdf"
    source_path.write_bytes(b"%PDF-1.4\n")

    po = app.PurchaseOrderData(
        customer_name='פדלון שפונדר ביצוע בע"מ',
        po_number="14520",
        po_date="25/06/2026",
        items=[],
    )

    monkeypatch.setattr(app, "managed_storage_root_folder_id", lambda: "root-folder")
    monkeypatch.setattr(app, "ensure_child_folder", lambda parent_id, title: f"{parent_id}:{title}")
    monkeypatch.setattr(
        app,
        "ensure_file_in_folder",
        lambda parent_id, file_path, drive_name=None: {
            "id": "drive-source-id",
            "name": drive_name or Path(file_path).name,
            "web_view_link": "https://drive.test/source",
        },
    )

    result = app._try_sync_source_po_to_drive_for_process(po, source_path)

    assert result["status"] == "ok"
    assert result["source_drive_file_id"] == "drive-source-id"
    assert result["source_drive_url"] == "https://drive.test/source"
    assert result["order_drive_folder_id"].startswith("root-folder:")


def test_process_payload_can_carry_source_drive_metadata():
    po = app.PurchaseOrderData(
        customer_name='פדלון שפונדר ביצוע בע"מ',
        customer_id="516087269",
        po_number="14520",
        po_date="25/06/2026",
        items=[],
    )
    payload = app._build_process_payload_from_po(
        po,
        "prod",
        "po.pdf",
        "/tmp/po.pdf",
        "drive-source-id",
    )
    payload["source_drive_url"] = "https://drive.test/source"
    payload["order_drive_folder_id"] = "order-folder-id"
    payload["order_drive_folder_url"] = "https://drive.test/folder"

    assert payload["source_drive_file_id"] == "drive-source-id"
    assert payload["source_drive_url"] == "https://drive.test/source"
    assert payload["order_drive_folder_id"] == "order-folder-id"
    assert payload["order_drive_folder_url"] == "https://drive.test/folder"


@pytest.mark.asyncio
async def test_haikon_payment_terms_from_po_survive_customer_enrichment(monkeypatch):
    class FakeGreenInvoiceClient:
        def __init__(self, **kwargs):
            pass

        async def get_existing_customer_details(self, customer_id):
            return {"name": 'הייקון (א.ק) בע"מ', "paymentTerms": 60}

        def _resolve_payment_days_for_customer(self, **kwargs):
            return 60

        def _merge_customer_data_into_po(self, po, customer_data):
            po.payment_terms_days = 60
            po.payment_terms_label = "שוטף + 60"
            return po

    monkeypatch.setattr(app, "GreenInvoiceClient", FakeGreenInvoiceClient)
    po = app.PurchaseOrderData(
        customer_name='הייקון (א.ק.) בע"מ',
        customer_id="516193430",
        payment_terms_days=90,
        payment_terms_label="שוטף 90",
        extra={"parser_name": "haikon"},
    )

    enriched = await app._enrich_po_for_process(
        po,
        {"base_url": "https://example.test", "api_key": "key", "api_secret": "secret"},
    )

    assert enriched.payment_terms_days == 90
    assert enriched.payment_terms_label == "שוטף 90"
