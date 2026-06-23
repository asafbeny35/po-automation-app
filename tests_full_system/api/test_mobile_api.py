from __future__ import annotations

import pytest

from tests_full_system.manifests.mobile import MOBILE_DOMAINS, MOBILE_SAFE_ENDPOINTS


@pytest.mark.api
@pytest.mark.requires_live_server
def test_mobile_auth_bootstrap_lists_users(api_client):
    response = api_client.get("/mobile/auth/bootstrap")
    assert response.status_code == 200
    payload = response.payload
    assert payload["status"] == "ok"
    assert isinstance(payload["auth_users"], list)
    assert payload["auth_users"], "Expected at least one auth user for mobile login"
    assert "selected_user_id" in payload
    assert "methods" in payload


@pytest.mark.api
@pytest.mark.requires_live_server
def test_mobile_dev_login_enables_authenticated_bootstrap(api_client):
    login = api_client.post(
        "/auth/dev-login",
        headers={"X-PO-Debug-Auth": "1"},
        json={"user_id": "asaf", "remember_me": True},
    )
    assert login.status_code == 200, login.payload
    payload = login.payload
    assert payload["status"] == "ok"

    auth_bootstrap = api_client.get("/mobile/auth/bootstrap")
    assert auth_bootstrap.status_code == 200
    assert auth_bootstrap.payload["authenticated"] is True


@pytest.mark.api
@pytest.mark.requires_live_server
def test_mobile_bootstrap_returns_snapshot_shape(api_client):
    api_client.post(
        "/auth/dev-login",
        headers={"X-PO-Debug-Auth": "1"},
        json={"user_id": "asaf", "remember_me": True},
    )
    response = api_client.get("/mobile/bootstrap", timeout=120)
    assert response.status_code == 200, response.payload
    payload = response.payload
    assert payload["status"] == "ok"
    assert isinstance(payload.get("generated_at"), str)
    assert isinstance(payload.get("source_label"), str)
    assert isinstance(payload.get("sections"), list)
    assert payload["sections"], "Expected at least one mobile dashboard section"


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize("domain", MOBILE_DOMAINS)
def test_mobile_domains_load_without_server_error(api_client, domain):
    api_client.post(
        "/auth/dev-login",
        headers={"X-PO-Debug-Auth": "1"},
        json={"user_id": "asaf", "remember_me": True},
    )
    response = api_client.get(f"/mobile/domains/{domain}", timeout=120)
    assert response.status_code == 200, f"{domain}: {response.payload}"
    payload = response.payload
    assert payload["status"] == "ok"
    assert payload["domain"] == domain
    assert isinstance(payload["rows"], list)
    assert isinstance(payload["count"], int)


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize("path", MOBILE_SAFE_ENDPOINTS)
def test_mobile_safe_endpoints_do_not_server_error(api_client, path):
    api_client.post(
        "/auth/dev-login",
        headers={"X-PO-Debug-Auth": "1"},
        json={"user_id": "asaf", "remember_me": True},
    )
    response = api_client.get(path, timeout=120)
    assert response.status_code < 500, f"{path}: {response.payload}"
