from __future__ import annotations

import pytest

from tests_full_system.manifests.routes import ROUTE_MANIFEST


_SLOW_SAFE_PATHS = {
    "/inventory-purchase-orders-state",
    "/finance-state",
    "/customers-state",
}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.timeout(300)
@pytest.mark.parametrize("route", [route for route in ROUTE_MANIFEST if route["safe"]], ids=lambda r: f'{r["method"]} {r["path"]}')
def test_safe_routes_do_not_crash(api_client, route):
    path = route["path"]
    if "{row_id}" in path:
        path = path.replace("{row_id}", "test-row-id")
    if "{asset_key}" in path:
        path = path.replace("{asset_key}", "nonexistent-asset-key-test")
    t = 300 if path in _SLOW_SAFE_PATHS else 60
    response = api_client.request(route["method"], path, timeout=t)
    if path in {
        "/google-drive/oauth/start",
        "/google-drive/oauth/callback",
        "/gmail-oauth/callback",
    } and response.status_code == 500:
        assert isinstance(response.payload, str)
        assert "<html" in response.payload.lower()
        assert "חיבור" in response.payload or "gmail" in response.payload.lower() or "google drive" in response.payload.lower()
        return
    assert response.status_code < 500, f"Safe route crashed: {route}"


@pytest.mark.api
def test_route_manifest_is_non_empty():
    assert ROUTE_MANIFEST
