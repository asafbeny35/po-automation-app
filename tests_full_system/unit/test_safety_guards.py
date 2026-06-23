from __future__ import annotations

import pytest

from tests_full_system.helpers.assertions import (
    assert_contains_named_test_marker,
    assert_sandbox_only,
    assert_test_whatsapp_number,
)
from tests_full_system.helpers.data_builders import (
    build_finalize_request,
    build_quote_finalize_request,
    build_test_order_payload,
    build_test_whatsapp_payload,
)
from tests_full_system.settings import SETTINGS


def test_order_builder_is_marked_as_test():
    payload = build_test_order_payload()
    assert_contains_named_test_marker(payload["customer_name"])
    assert_contains_named_test_marker(payload["project"])


def test_finalize_request_is_sandbox_only():
    request_payload = build_finalize_request()
    assert_sandbox_only(request_payload["mode"])


def test_quote_request_is_sandbox_only():
    request_payload = build_quote_finalize_request()
    assert_sandbox_only(request_payload["mode"])


def test_whatsapp_builder_targets_only_test_number():
    payload = build_test_whatsapp_payload()
    assert_test_whatsapp_number(payload["phone"], SETTINGS.whatsapp_test_number)


def test_assert_sandbox_only_rejects_prod():
    with pytest.raises(AssertionError):
        assert_sandbox_only("prod")
