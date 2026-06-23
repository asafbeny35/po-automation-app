from __future__ import annotations


def assert_sandbox_only(mode: str) -> None:
    normalized = str(mode or "").strip().lower()
    assert normalized == "sandbox", f"Only sandbox is allowed in tests, got: {mode!r}"


def assert_test_whatsapp_number(number: str, expected: str) -> None:
    normalized = "".join(ch for ch in str(number or "") if ch.isdigit())
    expected_normalized = "".join(ch for ch in str(expected or "") if ch.isdigit())
    assert normalized == expected_normalized, (
        f"WhatsApp target must be the dedicated test number {expected!r}, got {number!r}"
    )


def assert_contains_test_marker(value: str) -> None:
    assert "TEST" in str(value or "").upper(), f"Expected a visible TEST marker in value: {value!r}"


def assert_contains_named_test_marker(value: str) -> None:
    normalized = str(value or "")
    assert "TEST" in normalized.upper(), f"Expected a visible TEST marker in value: {value!r}"
    assert "נעלולי פלא" in normalized, f"Expected the visible fallback name 'נעלולי פלא' in value: {value!r}"
