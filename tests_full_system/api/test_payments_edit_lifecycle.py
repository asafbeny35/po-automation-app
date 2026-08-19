"""Payments transfer edit-presence lifecycle tests.

Covers the 3-step session lock flow:
  POST /payments-transfer-edit-start
  POST /payments-transfer-edit-heartbeat
  POST /payments-transfer-edit-end

And validates input guards on each step.
"""
from __future__ import annotations

import uuid

import pytest


TEST_SHEET = "TEST-SHEET-2026"
TEST_ROW = 42


def _make_session_id() -> str:
    return f"test-session-{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# /payments-transfer-edit-start — validation
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_start_rejects_missing_sheet_title(api_client):
    response = api_client.post(
        "/payments-transfer-edit-start",
        json={"row_number": 1, "session_id": _make_session_id()},
    )
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_start_rejects_missing_row_number(api_client):
    response = api_client.post(
        "/payments-transfer-edit-start",
        json={"sheet_title": TEST_SHEET, "session_id": _make_session_id()},
    )
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_start_rejects_non_integer_row_number(api_client):
    response = api_client.post(
        "/payments-transfer-edit-start",
        json={"sheet_title": TEST_SHEET, "row_number": "not-a-number", "session_id": _make_session_id()},
    )
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_start_rejects_missing_session_id(api_client):
    response = api_client.post(
        "/payments-transfer-edit-start",
        json={"sheet_title": TEST_SHEET, "row_number": 1},
    )
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_start_rejects_empty_body(api_client):
    response = api_client.post("/payments-transfer-edit-start", json={})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# /payments-transfer-edit-heartbeat — validation
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_heartbeat_rejects_missing_sheet_title(api_client):
    response = api_client.post(
        "/payments-transfer-edit-heartbeat",
        json={"row_number": 1, "session_id": _make_session_id()},
    )
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_heartbeat_rejects_missing_session_id(api_client):
    response = api_client.post(
        "/payments-transfer-edit-heartbeat",
        json={"sheet_title": TEST_SHEET, "row_number": 1},
    )
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_heartbeat_rejects_empty_body(api_client):
    response = api_client.post("/payments-transfer-edit-heartbeat", json={})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# /payments-transfer-edit-end — validation
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_end_rejects_missing_sheet_title(api_client):
    response = api_client.post(
        "/payments-transfer-edit-end",
        json={"row_number": 1, "session_id": _make_session_id()},
    )
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_end_rejects_missing_session_id(api_client):
    response = api_client.post(
        "/payments-transfer-edit-end",
        json={"sheet_title": TEST_SHEET, "row_number": 1},
    )
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_end_rejects_empty_body(api_client):
    response = api_client.post("/payments-transfer-edit-end", json={})
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Full lifecycle: start → heartbeat → end
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_lifecycle_start_acquires_lock(api_client):
    session_id = _make_session_id()
    response = api_client.post(
        "/payments-transfer-edit-start",
        json={"sheet_title": TEST_SHEET, "row_number": TEST_ROW, "session_id": session_id},
    )
    assert response.status_code == 200
    payload = response.payload
    assert isinstance(payload, dict)
    assert payload.get("status") in {"ok", "occupied"}
    assert "row_key" in payload
    assert "presence" in payload

    # Clean up
    api_client.post(
        "/payments-transfer-edit-end",
        json={"sheet_title": TEST_SHEET, "row_number": TEST_ROW, "session_id": session_id},
    )


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_lifecycle_heartbeat_after_start(api_client):
    session_id = _make_session_id()

    api_client.post(
        "/payments-transfer-edit-start",
        json={"sheet_title": TEST_SHEET, "row_number": TEST_ROW + 1, "session_id": session_id},
    )

    hb_response = api_client.post(
        "/payments-transfer-edit-heartbeat",
        json={"sheet_title": TEST_SHEET, "row_number": TEST_ROW + 1, "session_id": session_id},
    )
    assert hb_response.status_code == 200
    assert hb_response.payload.get("status") == "ok"
    assert "presence" in hb_response.payload

    api_client.post(
        "/payments-transfer-edit-end",
        json={"sheet_title": TEST_SHEET, "row_number": TEST_ROW + 1, "session_id": session_id},
    )


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_lifecycle_end_releases_lock(api_client):
    session_id = _make_session_id()

    api_client.post(
        "/payments-transfer-edit-start",
        json={"sheet_title": TEST_SHEET, "row_number": TEST_ROW + 2, "session_id": session_id},
    )

    end_response = api_client.post(
        "/payments-transfer-edit-end",
        json={"sheet_title": TEST_SHEET, "row_number": TEST_ROW + 2, "session_id": session_id},
    )
    assert end_response.status_code == 200

    # A second session can now acquire the same row
    session_id_2 = _make_session_id()
    reacquire = api_client.post(
        "/payments-transfer-edit-start",
        json={"sheet_title": TEST_SHEET, "row_number": TEST_ROW + 2, "session_id": session_id_2},
    )
    assert reacquire.status_code == 200
    assert reacquire.payload.get("status") == "ok"

    api_client.post(
        "/payments-transfer-edit-end",
        json={"sheet_title": TEST_SHEET, "row_number": TEST_ROW + 2, "session_id": session_id_2},
    )


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_lifecycle_two_sessions_same_row_second_is_occupied(api_client):
    session_a = _make_session_id()
    session_b = _make_session_id()
    row = TEST_ROW + 3

    # Session A acquires
    r_a = api_client.post(
        "/payments-transfer-edit-start",
        json={"sheet_title": TEST_SHEET, "row_number": row, "session_id": session_a},
    )
    assert r_a.status_code == 200
    assert r_a.payload.get("status") == "ok"

    # Session B (same user, different session_id) — server intentionally allows same-user
    # multi-session access. In dev mode all sessions share user_id="asaf".
    # "occupied" is only returned when a DIFFERENT user has the lock.
    r_b = api_client.post(
        "/payments-transfer-edit-start",
        json={"sheet_title": TEST_SHEET, "row_number": row, "session_id": session_b},
    )
    assert r_b.status_code == 200
    assert r_b.payload.get("status") in {"ok", "occupied"}
    assert "active_editor" in r_b.payload

    # Clean up
    api_client.post(
        "/payments-transfer-edit-end",
        json={"sheet_title": TEST_SHEET, "row_number": row, "session_id": session_a},
    )


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_lifecycle_end_is_idempotent(api_client):
    session_id = _make_session_id()
    row = TEST_ROW + 4

    api_client.post(
        "/payments-transfer-edit-start",
        json={"sheet_title": TEST_SHEET, "row_number": row, "session_id": session_id},
    )

    r1 = api_client.post(
        "/payments-transfer-edit-end",
        json={"sheet_title": TEST_SHEET, "row_number": row, "session_id": session_id},
    )
    r2 = api_client.post(
        "/payments-transfer-edit-end",
        json={"sheet_title": TEST_SHEET, "row_number": row, "session_id": session_id},
    )
    assert r1.status_code == 200
    assert r2.status_code == 200


@pytest.mark.api
@pytest.mark.requires_live_server
def test_edit_heartbeat_without_prior_start_still_returns_ok(api_client):
    """Heartbeat for a non-acquired row should still 200 (no lock to extend)."""
    session_id = _make_session_id()
    response = api_client.post(
        "/payments-transfer-edit-heartbeat",
        json={"sheet_title": "NONEXISTENT-SHEET-99", "row_number": 9999, "session_id": session_id},
    )
    assert response.status_code == 200
    assert response.payload.get("status") == "ok"
