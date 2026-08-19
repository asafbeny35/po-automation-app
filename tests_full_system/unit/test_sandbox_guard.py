"""Sandbox guard unit tests — enforce that all mutating payloads require mode=sandbox."""
from __future__ import annotations

import pytest

from tests_full_system.helpers.assertions import (
    assert_sandbox_only,
    assert_test_whatsapp_number,
    assert_contains_test_marker,
    assert_contains_named_test_marker,
)
from tests_full_system.helpers.data_builders import (
    build_finalize_request,
    build_quote_finalize_request,
    build_test_order_payload,
    build_test_whatsapp_payload,
    enforce_sandbox_request,
)
from tests_full_system.settings import SETTINGS


# ---------------------------------------------------------------------------
# Sandbox mode assertion helper
# ---------------------------------------------------------------------------

def test_assert_sandbox_only_passes_for_sandbox():
    assert_sandbox_only("sandbox")


def test_assert_sandbox_only_passes_for_uppercase():
    assert_sandbox_only("SANDBOX")


def test_assert_sandbox_only_passes_with_whitespace():
    assert_sandbox_only("  sandbox  ")


def test_assert_sandbox_only_rejects_production():
    with pytest.raises(AssertionError):
        assert_sandbox_only("production")


def test_assert_sandbox_only_rejects_empty():
    with pytest.raises(AssertionError):
        assert_sandbox_only("")


def test_assert_sandbox_only_rejects_none():
    with pytest.raises(AssertionError):
        assert_sandbox_only(None)


def test_assert_sandbox_only_rejects_prod_alias():
    with pytest.raises(AssertionError):
        assert_sandbox_only("prod")


# ---------------------------------------------------------------------------
# WhatsApp number guard
# ---------------------------------------------------------------------------

def test_assert_test_whatsapp_number_passes_exact_match():
    assert_test_whatsapp_number("0547720142", "0547720142")


def test_assert_test_whatsapp_number_country_prefix_is_different_digits():
    """The assertion helper does pure digit normalization — +972 vs 0 differ.
    This test documents the current behaviour rather than asserting it passes."""
    # 972547720142 != 0547720142 in raw digits, so this SHOULD fail in the current impl
    with pytest.raises(AssertionError):
        assert_test_whatsapp_number("+972547720142", "0547720142")


def test_assert_test_whatsapp_number_passes_with_dashes():
    assert_test_whatsapp_number("054-772-0142", "0547720142")


def test_assert_test_whatsapp_number_rejects_wrong_number():
    with pytest.raises(AssertionError):
        assert_test_whatsapp_number("0500000000", "0547720142")


def test_assert_test_whatsapp_number_rejects_empty():
    with pytest.raises(AssertionError):
        assert_test_whatsapp_number("", "0547720142")


# ---------------------------------------------------------------------------
# Test marker assertions
# ---------------------------------------------------------------------------

def test_assert_contains_test_marker_passes():
    assert_contains_test_marker("TEST | שם משהו")


def test_assert_contains_test_marker_passes_lowercase():
    assert_contains_test_marker("test data")


def test_assert_contains_test_marker_rejects_no_marker():
    with pytest.raises(AssertionError):
        assert_contains_test_marker("לקוח אמיתי")


def test_assert_contains_named_test_marker_passes():
    assert_contains_named_test_marker("TEST | נעלולי פלא | משהו")


def test_assert_contains_named_test_marker_rejects_missing_hebrew():
    with pytest.raises(AssertionError):
        assert_contains_named_test_marker("TEST | something without hebrew fallback")


def test_assert_contains_named_test_marker_rejects_empty():
    with pytest.raises(AssertionError):
        assert_contains_named_test_marker("")


# ---------------------------------------------------------------------------
# Data builders
# ---------------------------------------------------------------------------

def test_build_test_order_payload_is_sandbox_safe():
    payload = build_test_order_payload()
    assert_contains_named_test_marker(payload["customer_name"])
    assert_contains_named_test_marker(payload["project"])
    assert_contains_named_test_marker(payload["contact_name"])
    assert_contains_named_test_marker(payload["footer_text"])


def test_build_test_order_payload_has_required_fields():
    payload = build_test_order_payload()
    required = [
        "po_number", "po_date", "customer_name", "customer_id",
        "customer_email", "customer_phone", "subtotal", "vat", "total",
        "items", "ordered_items",
    ]
    for field in required:
        assert field in payload, f"Missing required field: {field}"


def test_build_test_order_payload_math_is_consistent():
    payload = build_test_order_payload()
    assert abs(payload["subtotal"] + payload["vat"] - payload["total"]) < 0.01


def test_build_finalize_request_mode_is_sandbox():
    req = build_finalize_request()
    assert req["mode"] == "sandbox"
    enforce_sandbox_request(req)


def test_build_finalize_request_delivery_only():
    req = build_finalize_request("delivery_only")
    assert req["document_mode"] == "delivery_only"
    assert req["mode"] == "sandbox"


def test_build_finalize_request_invoice_only():
    req = build_finalize_request("invoice_only")
    assert req["document_mode"] == "invoice_only"


def test_build_finalize_request_full_mode():
    req = build_finalize_request("full")
    assert req["document_mode"] == "full"


def test_build_finalize_request_partial_delivery_false_by_default():
    req = build_finalize_request()
    assert req["data"]["partial_delivery"] is False


def test_build_finalize_request_partial_delivery_true():
    req = build_finalize_request("full", partial_delivery=True)
    assert req["data"]["partial_delivery"] is True


def test_build_quote_finalize_request_is_sandbox():
    req = build_quote_finalize_request()
    assert req["mode"] == "sandbox"
    assert req["data"]["manual_document_kind"] == "quote"


def test_build_test_whatsapp_payload_uses_test_number():
    payload = build_test_whatsapp_payload()
    assert_test_whatsapp_number(payload["phone"], SETTINGS.whatsapp_test_number)


def test_build_test_whatsapp_payload_has_test_marker():
    payload = build_test_whatsapp_payload()
    assert_contains_named_test_marker(payload["message"])


def test_enforce_sandbox_request_passes_sandbox():
    req = {"mode": "sandbox", "data": {}}
    result = enforce_sandbox_request(req)
    assert result is req  # same object returned


def test_enforce_sandbox_request_rejects_production():
    with pytest.raises(AssertionError):
        enforce_sandbox_request({"mode": "production", "data": {}})


def test_data_builders_produce_unique_labels():
    """Consecutive calls should yield different labels (counter increments)."""
    p1 = build_test_order_payload()
    p2 = build_test_order_payload()
    assert p1["customer_name"] != p2["customer_name"]


# ---------------------------------------------------------------------------
# Settings sanity
# ---------------------------------------------------------------------------

def test_settings_sandbox_mode_is_sandbox():
    assert SETTINGS.sandbox_mode.strip().lower() == "sandbox"


def test_settings_allow_prod_is_false():
    assert SETTINGS.allow_prod_creation is False


def test_settings_whatsapp_number_non_empty():
    assert SETTINGS.whatsapp_test_number.strip() != ""


def test_settings_base_url_non_empty():
    assert SETTINGS.base_url.strip() != ""


def test_settings_visible_test_tag_non_empty():
    assert SETTINGS.visible_test_tag.strip() != ""


def test_settings_visible_test_name_base_non_empty():
    assert SETTINGS.visible_test_name_base.strip() != ""
