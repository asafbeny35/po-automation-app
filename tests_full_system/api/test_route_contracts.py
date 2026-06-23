from __future__ import annotations

import pytest

from tests_full_system.manifests.routes import ROUTE_MANIFEST


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize("route", [route for route in ROUTE_MANIFEST if route["safe"]], ids=lambda r: f'{r["method"]} {r["path"]}')
def test_safe_routes_do_not_crash(api_client, route):
    path = route["path"]
    if "{row_id}" in path:
        path = path.replace("{row_id}", "test-row-id")
    response = api_client.request(route["method"], path)
    assert response.status_code < 500, f"Safe route crashed: {route}"


@pytest.mark.api
def test_route_manifest_is_non_empty():
    assert ROUTE_MANIFEST
