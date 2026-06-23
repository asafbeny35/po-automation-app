from __future__ import annotations

from datetime import date
from itertools import count

from tests_full_system.helpers.assertions import (
    assert_contains_named_test_marker,
    assert_sandbox_only,
    assert_test_whatsapp_number,
)
from tests_full_system.settings import SETTINGS

_TEST_NAME_COUNTER = count(1)


def build_test_label(prefix: str) -> str:
    serial = next(_TEST_NAME_COUNTER)
    return (
        f"{SETTINGS.visible_test_tag} | "
        f"{SETTINGS.visible_test_name_base} {serial} | "
        f"{prefix} | "
        f"{date.today().isoformat()}"
    )


def build_test_order_payload() -> dict:
    payload = {
        "mode": "manual",
        "manual_entry": True,
        "manual_document_kind": "order",
        "po_number": f"TEST-{date.today().strftime('%Y%m%d')}-001",
        "po_date": date.today().strftime("%d/%m/%Y"),
        "customer_name": build_test_label("לקוח הזמנה"),
        "customer_id": "999999999",
        "customer_email": "test@example.com",
        "customer_phone": "0547720142",
        "delivery_address": "כתובת TEST 1",
        "project": build_test_label("פרויקט"),
        "contact_name": build_test_label("איש קשר"),
        "contact_phone": "0547720142",
        "payment_terms_days": "30",
        "payment_terms_label": "שוטף + 30",
        "subtotal": 100.0,
        "vat": 18.0,
        "total": 118.0,
        "item_description": build_test_label("מוצר"),
        "item_sku": "TEST-SKU-001",
        "item_unit": "יחידה",
        "item_quantity": 1,
        "item_unit_price": 100.0,
        "item_line_total": 100.0,
        "items": [
            {
                "description": build_test_label("מוצר"),
                "sku": "TEST-SKU-001",
                "unit": "יחידה",
                "quantity": 1,
                "unit_price": 100.0,
                "line_total": 100.0,
            }
        ],
        "ordered_items": [
            {
                "description": build_test_label("מוצר"),
                "sku": "TEST-SKU-001",
                "unit": "יחידה",
                "quantity": 1,
                "unit_price": 100.0,
                "line_total": 100.0,
            }
        ],
        "footer_text": build_test_label("הערה"),
        "partial_delivery": False,
        "label_split_rows": [],
    }
    assert_contains_named_test_marker(payload["customer_name"])
    return payload


def build_finalize_request(document_mode: str = "full", *, partial_delivery: bool = False) -> dict:
    data = build_test_order_payload()
    data["partial_delivery"] = partial_delivery
    return {
        "mode": "sandbox",
        "document_mode": document_mode,
        "data": data,
    }


def build_quote_finalize_request() -> dict:
    data = build_test_order_payload()
    data["manual_document_kind"] = "quote"
    return {"mode": "sandbox", "data": data}


def build_test_whatsapp_payload() -> dict:
    payload = {
        "phone": SETTINGS.whatsapp_test_number,
        "message": build_test_label("WhatsApp"),
    }
    assert_test_whatsapp_number(payload["phone"], SETTINGS.whatsapp_test_number)
    return payload


def enforce_sandbox_request(payload: dict) -> dict:
    assert_sandbox_only(payload.get("mode", ""))
    return payload
