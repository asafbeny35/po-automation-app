from __future__ import annotations

from pathlib import Path

import pytest

from tests_full_system.helpers.data_builders import build_finalize_request, build_quote_finalize_request
from tests_full_system.settings import SETTINGS


SAMPLE_PURCHASE_ORDER_PDF = (
    SETTINGS.project_root
    / "output"
    / "Production Docs"
    / "ברוש ניר עבודות הנדסה ובנין בע״מ - PO26001090"
    / "הדפסת הזמנת רכש - PO26001090.pdf"
)


def _assert_output_file_exists(relative_output_path: str) -> None:
    assert relative_output_path, "expected non-empty relative output path"
    absolute_path = SETTINGS.project_root / "output" / relative_output_path
    assert absolute_path.exists(), f"expected generated file to exist: {absolute_path}"


def _process_real_purchase_order_pdf(api_client, pdf_path: Path) -> dict:
    with pdf_path.open("rb") as handle:
        response = api_client.post(
            "/process",
            files={"file": (pdf_path.name, handle, "application/pdf")},
            data={"mode": "sandbox"},
        )
    assert response.status_code == 200, response.payload
    assert isinstance(response.payload, dict), response.payload
    return response.payload


def _finalize_processed_payload(
    api_client,
    processed_payload: dict,
    *,
    document_mode: str,
    extra_data: dict | None = None,
) -> dict:
    request_payload = {
        "mode": "sandbox",
        "document_mode": document_mode,
        "data": {
            **processed_payload,
            **(extra_data or {}),
        },
    }
    response = api_client.post("/finalize", json=request_payload, timeout=180.0)
    assert response.status_code == 200, response.payload
    assert isinstance(response.payload, dict), response.payload
    return response.payload


def _normalize_hebrew_quotes(value: str) -> str:
    return str(value).replace("״", '"').replace("”", '"').replace("׳", "'").replace("’", "'")


@pytest.mark.api
def test_finalize_request_contains_test_markers():
    payload = build_finalize_request()
    assert "TEST" in payload["data"]["customer_name"]
    assert payload["data"]["customer_phone"] == "0547720142"


@pytest.mark.api
def test_finalize_request_contains_ordered_items():
    payload = build_finalize_request()
    assert isinstance(payload["data"]["ordered_items"], list)
    assert payload["data"]["ordered_items"]


@pytest.mark.api
def test_finalize_request_can_mark_partial_delivery():
    payload = build_finalize_request(partial_delivery=True)
    assert payload["data"]["partial_delivery"] is True


@pytest.mark.api
def test_finalize_quote_request_contains_test_markers():
    payload = build_quote_finalize_request()
    assert "TEST" in payload["data"]["customer_name"]
    assert payload["mode"] == "sandbox"


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
@pytest.mark.sandbox_only
def test_finalize_endpoint_reachable_with_manual_order_shape(api_client):
    payload = build_finalize_request()
    response = api_client.post("/finalize", json=payload)
    assert response.status_code in {200, 400, 401, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
@pytest.mark.sandbox_only
def test_finalize_quote_endpoint_reachable_with_manual_quote_shape(api_client):
    payload = build_quote_finalize_request()
    response = api_client.post("/finalize-quote", json=payload)
    assert response.status_code in {200, 400, 401, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
@pytest.mark.sandbox_only
def test_process_real_purchase_order_pdf_returns_expected_parsed_payload(api_client, ensure_sandbox_guard):
    assert SAMPLE_PURCHASE_ORDER_PDF.exists(), f"missing sample PDF fixture: {SAMPLE_PURCHASE_ORDER_PDF}"
    payload = _process_real_purchase_order_pdf(api_client, SAMPLE_PURCHASE_ORDER_PDF)

    assert payload["mode"] == "sandbox"
    assert payload["po_number"] == "PO26001090"
    assert _normalize_hebrew_quotes(payload["customer_name"]) == 'ברוש ניר עבודות הנדסה ובנין בע"מ'
    assert payload["customer_id"] == "512598749"
    assert payload["payment_terms_label"] == "שוטף + 60"
    assert str(payload["payment_terms_days"]) == "60"
    assert payload["source_file"] == SAMPLE_PURCHASE_ORDER_PDF.name
    assert Path(payload["source_file_path"]).exists()
    assert payload["items_count"] >= 2
    assert isinstance(payload["items"], list)
    assert len(payload["items"]) >= 2
    assert "מגן לדלת" in str(payload["item_description"])
    assert any("מגן לדלת" in str(item.get("description") or "") for item in payload["items"])


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
@pytest.mark.sandbox_only
def test_finalize_full_from_processed_pdf_returns_all_required_artifacts(api_client, ensure_sandbox_guard):
    processed_payload = _process_real_purchase_order_pdf(api_client, SAMPLE_PURCHASE_ORDER_PDF)
    payload = _finalize_processed_payload(api_client, processed_payload, document_mode="full")

    assert payload["status"] == "ok"
    assert payload["mode"] == "sandbox"
    assert payload["document_mode"] == "full"
    assert str(payload["delivery_document_number"]).strip()
    assert str(payload["invoice_document_number"]).strip()
    assert len([item for item in payload["files"] if item]) == 2
    assert len(payload["label_files"]) >= 2
    assert payload["merged_file"]
    assert payload["source_po_file"]
    assert len(payload["all_generated_files"]) >= 6
    assert set(payload["files"]).issubset(set(payload["all_generated_files"]))
    assert set(payload["label_files"]).issubset(set(payload["all_generated_files"]))
    assert payload["merged_file"] in payload["all_generated_files"]
    assert payload["source_po_file"] in payload["all_generated_files"]

    for relative_path in payload["all_generated_files"]:
        _assert_output_file_exists(relative_path)

    drive_sync_result = payload["drive_sync_result"]
    assert drive_sync_result["status"] == "ok"
    uploaded_files = list(drive_sync_result.get("uploaded_files") or [])
    uploaded_names = {str(item.get("name") or "").strip() for item in uploaded_files}
    assert len(uploaded_files) >= 6
    assert any(name.endswith(".pdf") and "delivery" in name for name in uploaded_names)
    assert any(name.endswith(".pdf") and "invoice" in name for name in uploaded_names)
    assert any("כל המסמכים" in name for name in uploaded_names)
    assert SAMPLE_PURCHASE_ORDER_PDF.name in uploaded_names
    assert len(payload["label_drive_file_ids"]) == len(payload["label_files"])

    history_result = payload["history_result"]
    assert history_result["status"] == "ok"
    history_row = history_result["row"]
    assert history_row["document_mode"] == "full"
    assert history_row["po_number"] == processed_payload["po_number"]
    assert str(history_row["delivery_document_number"]) == str(payload["delivery_document_number"])
    assert str(history_row["tax_invoice_number"]) == str(payload["invoice_document_number"])
    assert str(history_row["merged_drive_file_id"]).strip()
    assert str(history_row["invoice_drive_file_id"]).strip()
    assert str(history_row["delivery_drive_file_id"]).strip()

    whatsapp_send_result = payload["whatsapp_send_result"]
    assert whatsapp_send_result["status"] in {"ok", "skipped", "error"}
    if whatsapp_send_result["status"] == "ok":
        assert whatsapp_send_result.get("targets")
    if whatsapp_send_result["status"] == "error":
        assert str(whatsapp_send_result.get("error") or "").strip()


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
@pytest.mark.sandbox_only
def test_finalize_delivery_only_from_processed_pdf_skips_invoice_artifacts(api_client, ensure_sandbox_guard):
    processed_payload = _process_real_purchase_order_pdf(api_client, SAMPLE_PURCHASE_ORDER_PDF)
    payload = _finalize_processed_payload(api_client, processed_payload, document_mode="delivery_only")

    assert payload["status"] == "ok"
    assert payload["document_mode"] == "delivery_only"
    assert str(payload["delivery_document_number"]).strip()
    assert not str(payload["invoice_document_number"]).strip()
    assert payload["delivery_pdf_path"]
    assert not payload["invoice_pdf_path"]
    assert payload["merged_file"]
    assert payload["source_po_file"]
    assert payload["transport_label_file"] == ""
    assert payload["files"][0]
    assert payload["files"][1] == ""
    assert payload["merged_file"] in payload["all_generated_files"]
    assert payload["source_po_file"] in payload["all_generated_files"]
    assert not any("invoice_" in path for path in payload["all_generated_files"])

    for relative_path in payload["all_generated_files"]:
        _assert_output_file_exists(relative_path)

    history_row = payload["history_result"]["row"]
    assert history_row["document_mode"] == "delivery_only"
    assert history_row["po_number"] == processed_payload["po_number"]
    assert str(history_row["tax_invoice_number"] or "").strip() == ""
    assert "לא נוצרה חשבונית מס" in str(history_row["order_status_tag"] or "")


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
@pytest.mark.sandbox_only
def test_finalize_invoice_only_from_processed_pdf_links_to_existing_delivery(api_client, ensure_sandbox_guard):
    processed_payload = _process_real_purchase_order_pdf(api_client, SAMPLE_PURCHASE_ORDER_PDF)
    delivery_payload = _finalize_processed_payload(api_client, processed_payload, document_mode="delivery_only")
    payload = _finalize_processed_payload(
        api_client,
        processed_payload,
        document_mode="invoice_only",
        extra_data={
            "delivery_document_id": delivery_payload["delivery_document_id"],
            "delivery_document_number": delivery_payload["delivery_document_number"],
        },
    )

    assert payload["status"] == "ok"
    assert payload["document_mode"] == "invoice_only"
    assert str(payload["invoice_document_number"]).strip()
    assert str(payload["delivery_document_id"]).strip() == str(delivery_payload["delivery_document_id"]).strip()
    assert str(payload["delivery_document_number"]).strip() == str(delivery_payload["delivery_document_number"]).strip()
    assert not payload["delivery_pdf_path"]
    assert payload["invoice_pdf_path"]
    assert payload["files"][0] == ""
    assert payload["files"][1]
    assert payload["merged_file"] == ""
    assert payload["label_files"] == []
    assert payload["source_po_file"]
    assert payload["source_po_file"] in payload["all_generated_files"]
    assert not any("כל המסמכים" in path for path in payload["all_generated_files"])
    assert not any("label_" in path for path in payload["all_generated_files"])

    for relative_path in payload["all_generated_files"]:
        _assert_output_file_exists(relative_path)

    drive_sync_result = payload["drive_sync_result"]
    assert drive_sync_result["status"] == "ok"
    uploaded_names = {
        str(item.get("name") or "").strip()
        for item in list(drive_sync_result.get("uploaded_files") or [])
    }
    assert SAMPLE_PURCHASE_ORDER_PDF.name in uploaded_names
    assert any(name.endswith(".pdf") and "invoice" in name for name in uploaded_names)
    assert not any("כל המסמכים" in name for name in uploaded_names)

    history_row = payload["history_result"]["row"]
    assert history_row["document_mode"] == "invoice_only"
    assert str(history_row["tax_invoice_number"]).strip() == str(payload["invoice_document_number"]).strip()
    assert str(history_row["delivery_document_number"]).strip() == str(delivery_payload["delivery_document_number"]).strip()
