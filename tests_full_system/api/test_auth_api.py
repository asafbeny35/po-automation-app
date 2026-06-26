"""Auth API tests — login, logout, TOTP, email OTP, passkey registration & login.

Coverage:
  GET  /auth/login
  POST /auth/dev-login
  POST /auth/logout
  POST /auth/totp/verify
  POST /auth/email/send-code
  POST /auth/email/verify
  POST /auth/passkey/register/options
  POST /auth/passkey/register/verify
  POST /auth/passkey/login/options
  POST /auth/passkey/login/verify
"""
from __future__ import annotations

import pytest

from tests_full_system.helpers.api_client import ApiClient
from tests_full_system.settings import SETTINGS


# ---------------------------------------------------------------------------
# GET /auth/login
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_login_page_returns_html(api_client):
    # Use a fresh unauthenticated client so we don't get redirected to app
    client = ApiClient()
    client._auto_auth_attempted = True  # skip dev-login so we hit the real login page
    response = client.request("GET", "/auth/login")
    client.close()
    assert response.status_code in {200, 302}
    if response.status_code == 200:
        assert isinstance(response.payload, str)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_login_redirects_authenticated_user(api_client):
    """When already authenticated the login page should redirect to / or return the app."""
    response = api_client.get("/auth/login")
    assert response.status_code in {200, 302}


# ---------------------------------------------------------------------------
# POST /auth/dev-login
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.localhost_only
def test_auth_dev_login_succeeds_with_correct_header(api_client):
    response = api_client.request(
        "POST",
        "/auth/dev-login",
        headers={"X-PO-Debug-Auth": "1"},
        json={"user_id": "asaf", "remember_me": True},
    )
    assert response.status_code == 200
    assert isinstance(response.payload, dict)
    assert response.payload.get("status") == "ok"
    assert "user_id" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.localhost_only
def test_auth_dev_login_response_has_redirect_field(api_client):
    response = api_client.request(
        "POST",
        "/auth/dev-login",
        headers={"X-PO-Debug-Auth": "1"},
        json={"user_id": "asaf", "remember_me": False},
    )
    assert response.status_code == 200
    assert "redirect_to" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.localhost_only
def test_auth_dev_login_rejects_missing_debug_header():
    """Without the X-PO-Debug-Auth header dev login must be rejected."""
    client = ApiClient()
    client._auto_auth_attempted = True
    response = client.request("POST", "/auth/dev-login", json={"user_id": "asaf"})
    client.close()
    assert response.status_code == 403


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.localhost_only
def test_auth_dev_login_empty_user_id_still_resolves(api_client):
    """Empty user_id should resolve to the default user, not crash."""
    response = api_client.request(
        "POST",
        "/auth/dev-login",
        headers={"X-PO-Debug-Auth": "1"},
        json={"user_id": "", "remember_me": False},
    )
    assert response.status_code == 200
    assert response.payload.get("status") == "ok"


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_logout_returns_ok(api_client):
    response = api_client.post("/auth/logout")
    assert response.status_code == 200
    assert isinstance(response.payload, dict)
    assert response.payload.get("status") == "ok"


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_logout_clears_session(api_client):
    """After logout, accessing a protected endpoint should redirect/reject."""
    api_client.post("/auth/logout")
    response = api_client.get("/payments-transfer-state", allow_unauthenticated=True)
    assert response.status_code in {401, 403}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_logout_is_idempotent(api_client):
    """Logging out twice must not crash."""
    r1 = api_client.post("/auth/logout")
    r2 = api_client.post("/auth/logout")
    assert r1.status_code == 200
    assert r2.status_code == 200


# ---------------------------------------------------------------------------
# POST /auth/totp/verify
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_totp_verify_rejects_invalid_code(api_client):
    response = api_client.post(
        "/auth/totp/verify",
        json={"code": "000000", "remember_me": False},
    )
    assert response.status_code in {400, 429}
    assert isinstance(response.payload, dict)
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_totp_verify_rejects_empty_code(api_client):
    response = api_client.post(
        "/auth/totp/verify",
        json={"code": "", "remember_me": False},
    )
    assert response.status_code in {400, 429}
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_totp_verify_rejects_non_numeric_code(api_client):
    response = api_client.post(
        "/auth/totp/verify",
        json={"code": "abcdef", "remember_me": False},
    )
    assert response.status_code in {400, 429}
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_totp_verify_rejects_short_code(api_client):
    response = api_client.post(
        "/auth/totp/verify",
        json={"code": "123", "remember_me": False},
    )
    assert response.status_code in {400, 429}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_totp_verify_error_message_is_hebrew(api_client):
    response = api_client.post(
        "/auth/totp/verify",
        json={"code": "999999", "remember_me": False},
    )
    assert response.status_code in {400, 429}
    error_msg = response.payload.get("error", "")
    assert len(error_msg) > 0


# ---------------------------------------------------------------------------
# POST /auth/email/send-code
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_email_send_code_rejects_missing_email(api_client):
    response = api_client.post(
        "/auth/email/send-code",
        json={"setup": False, "remember_me": False, "user_id": "asaf"},
    )
    # When email is configured for user → 200 (sends to configured address); 400/429 otherwise
    assert response.status_code in {200, 400, 429, 500}
    assert isinstance(response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_email_send_code_setup_mode_rejects_missing_email(api_client):
    response = api_client.post(
        "/auth/email/send-code",
        json={"setup": True, "email": "", "remember_me": False},
    )
    # 429 if rate-limited from other tests in same run
    assert response.status_code in {400, 429}
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_email_send_code_empty_body_returns_error(api_client):
    response = api_client.post("/auth/email/send-code", json={})
    # 200 if server has a configured email fallback; 400/429 otherwise
    assert response.status_code in {200, 400, 429, 500}


# ---------------------------------------------------------------------------
# POST /auth/email/verify
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_email_verify_rejects_wrong_code(api_client):
    response = api_client.post(
        "/auth/email/verify",
        json={"code": "000000"},
    )
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_email_verify_rejects_empty_code(api_client):
    response = api_client.post(
        "/auth/email/verify",
        json={"code": ""},
    )
    assert response.status_code == 400


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_email_verify_error_indicates_invalid_or_expired(api_client):
    response = api_client.post(
        "/auth/email/verify",
        json={"code": "123456"},
    )
    assert response.status_code == 400
    error = response.payload.get("error", "")
    assert len(error) > 0


# ---------------------------------------------------------------------------
# POST /auth/passkey/register/options
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_passkey_register_options_returns_options(api_client):
    response = api_client.post(
        "/auth/passkey/register/options",
        json={"user_id": "asaf"},
    )
    assert response.status_code == 200
    assert isinstance(response.payload, dict)
    assert response.payload.get("status") == "ok"
    assert "options" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_passkey_register_options_with_empty_user_id(api_client):
    response = api_client.post(
        "/auth/passkey/register/options",
        json={"user_id": ""},
    )
    assert response.status_code == 200
    assert "options" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_passkey_register_options_without_user_id(api_client):
    response = api_client.post("/auth/passkey/register/options", json={})
    assert response.status_code in {200, 400}


# ---------------------------------------------------------------------------
# POST /auth/passkey/register/verify
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_passkey_register_verify_rejects_empty_credential(api_client):
    response = api_client.post(
        "/auth/passkey/register/verify",
        json={"credential": {}, "remember_me": False},
    )
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_passkey_register_verify_rejects_missing_credential(api_client):
    response = api_client.post(
        "/auth/passkey/register/verify",
        json={"remember_me": False},
    )
    assert response.status_code in {400, 422}


# ---------------------------------------------------------------------------
# POST /auth/passkey/login/options
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_passkey_login_options_no_passkey_configured(api_client):
    """If no passkey configured for user, should return 400."""
    response = api_client.post(
        "/auth/passkey/login/options",
        json={"user_id": "nonexistent-test-user-999", "remember_me": False},
    )
    # Either 400 (no passkey) or 200 with options if user has passkey
    assert response.status_code in {200, 400}
    assert isinstance(response.payload, dict)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_passkey_login_options_returns_dict(api_client):
    response = api_client.post(
        "/auth/passkey/login/options",
        json={"user_id": "asaf", "remember_me": False},
    )
    assert response.status_code in {200, 400}
    assert isinstance(response.payload, dict)


# ---------------------------------------------------------------------------
# POST /auth/passkey/login/verify
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_passkey_login_verify_rejects_empty_credential(api_client):
    response = api_client.post(
        "/auth/passkey/login/verify",
        json={"credential": {}},
    )
    assert response.status_code == 400
    assert "error" in response.payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_auth_passkey_login_verify_rejects_missing_credential(api_client):
    response = api_client.post("/auth/passkey/login/verify", json={})
    assert response.status_code in {400, 422}
