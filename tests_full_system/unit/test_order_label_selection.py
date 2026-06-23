from __future__ import annotations

from pathlib import Path

from app import (
    _build_process_payload_from_po,
    _merchandise_po_items,
    _should_generate_label_for_po_item,
)
from services.models import POItem, PurchaseOrderData


def test_label_defaults_skip_service_and_shipping_rows():
    product = POItem(description="מגן דלת פרו דור", quantity=10, unit="יחידה")
    labour = POItem(description="עבודה", quantity=1, unit="יחידה")
    shipping = POItem(description="הובלה", quantity=1, unit="יחידה")

    assert _should_generate_label_for_po_item(product) is True
    assert _should_generate_label_for_po_item(labour) is False
    assert _should_generate_label_for_po_item(shipping) is False


def test_explicit_label_override_allows_service_row():
    labour = POItem(description="עבודה", quantity=1, unit="יחידה", generate_label=True)

    assert _should_generate_label_for_po_item(labour) is True


def test_process_payload_exposes_per_item_label_decision():
    po = PurchaseOrderData(
        po_number="PO-TEST-1",
        customer_name="לקוח בדיקה",
        items=[
            POItem(description="מגן דלת", quantity=5, unit="יחידה"),
            POItem(description="עבודה", quantity=1, unit="יחידה"),
            POItem(description="הובלה", quantity=1, unit="יחידה"),
            POItem(description="עבודה מיוחדת", quantity=1, unit="יחידה", generate_label=True),
        ],
    )

    payload = _build_process_payload_from_po(po, "sandbox", "test.pdf", Path("/tmp/test.pdf"))

    assert payload["item_description"] == "מגן דלת"
    assert payload["item_generate_label"] is True
    assert [item["generate_label"] for item in payload["items"]] == [True, False, False, True]


def test_merchandise_items_follow_explicit_and_default_rules():
    po = PurchaseOrderData(
        items=[
            POItem(description="מגן דלת", quantity=5, unit="יחידה"),
            POItem(description="עבודה", quantity=1, unit="יחידה"),
            POItem(description="הובלה", quantity=1, unit="יחידה"),
            POItem(description="שירות התקנה", quantity=1, unit="יחידה", generate_label=True),
        ]
    )

    filtered = _merchandise_po_items(po)

    assert [item.description for item in filtered] == ["מגן דלת", "שירות התקנה"]
