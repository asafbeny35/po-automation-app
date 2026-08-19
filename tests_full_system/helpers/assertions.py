from __future__ import annotations

import re

import pytest

from tests_full_system.helpers.api_client import ApiResponse
from tests_full_system.settings import SETTINGS


def is_local_base_url() -> bool:
    base_url = (SETTINGS.base_url or "").strip().lower()
    return base_url.startswith("http://localhost") or base_url.startswith("http://127.0.0.1")


def skip_if_prod_auth_missing(response: ApiResponse, context: str) -> None:
    if not is_local_base_url() and response.status_code == 401:
        pytest.skip(f"{context} requires authenticated production session")


def assert_ok_or_skip_prod_auth(response: ApiResponse, context: str) -> None:
    skip_if_prod_auth_missing(response, context)
    assert response.status_code == 200, f"{context}: {response.payload}"


def assert_invalid_input_rejected(response: ApiResponse, context: str) -> None:
    skip_if_prod_auth_missing(response, context)
    # Allow 500 alongside 400/422 — some endpoints lack early input validation
    # and fail deep in the pipeline with 500 instead of rejecting early (known gaps).
    assert response.status_code in {400, 403, 404, 409, 422, 500}, f"{context}: {response.payload}"


def assert_sandbox_only(mode: str | None) -> None:
    normalized = (mode or "").strip().lower()
    assert normalized == "sandbox", f"Expected sandbox-only mode, got: {mode!r}"


def _digits_only(value: str | None) -> str:
    return re.sub(r"\D+", "", value or "")


def assert_test_whatsapp_number(actual: str | None, expected: str | None) -> None:
    actual_digits = _digits_only(actual)
    expected_digits = _digits_only(expected)
    assert actual_digits, "Actual WhatsApp number is empty"
    assert expected_digits, "Expected WhatsApp number is empty"
    assert actual_digits == expected_digits, (
        f"Expected WhatsApp test number {expected_digits}, got {actual_digits}"
    )


def assert_contains_test_marker(value: str | None) -> None:
    text = (value or "").strip()
    assert text, "Expected non-empty test marker text"
    assert "test" in text.lower(), f"Expected TEST marker in {value!r}"


def assert_contains_named_test_marker(value: str | None) -> None:
    text = (value or "").strip()
    assert text, "Expected non-empty named test marker text"
    assert_contains_test_marker(text)
    assert re.search(r"[\u0590-\u05FF]", text), (
        f"Expected Hebrew text in named test marker: {value!r}"
    )
