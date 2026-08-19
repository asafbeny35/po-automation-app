from __future__ import annotations

import pytest

from tests_full_system.helpers.assertions import assert_ok_or_skip_prod_auth, skip_if_prod_auth_missing
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
def test_mobile_authenticated_bootstrap_is_reachable(api_client):
    auth_bootstrap = api_client.get("/mobile/auth/bootstrap")
    assert auth_bootstrap.status_code == 200
    assert isinstance(auth_bootstrap.payload.get("authenticated"), bool)


@pytest.mark.api
@pytest.mark.requires_live_server
def test_mobile_bootstrap_returns_snapshot_shape(api_client):
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
    response = api_client.get(f"/mobile/domains/{domain}", timeout=120)
    assert_ok_or_skip_prod_auth(response, domain)
    payload = response.payload
    assert payload["status"] == "ok"
    assert payload["domain"] == domain
    assert isinstance(payload["rows"], list)
    assert isinstance(payload["count"], int)


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize("path", MOBILE_SAFE_ENDPOINTS)
def test_mobile_safe_endpoints_do_not_server_error(api_client, path):
    response = api_client.get(path, timeout=120)
    skip_if_prod_auth_missing(response, path)
    assert response.status_code < 500, f"{path}: {response.payload}"
