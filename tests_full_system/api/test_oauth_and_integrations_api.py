from __future__ import annotations

import pytest


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize(
    "path",
    [
        "/gmail-oauth/status",
        "/google-drive/oauth/status",
        "/pazomat-state",
        "/sibus-state",
        "/finance-invoices-drive-folder",
        "/marketing-drive-folder",
    ],
)
def test_integration_status_endpoints_available(api_client, path):
    response = api_client.get(path)
    assert response.status_code < 500
