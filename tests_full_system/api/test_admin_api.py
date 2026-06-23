from __future__ import annotations

import pytest


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize(
    "path",
    [
        "/admin-drive-folder",
        "/insurance-drive-folder",
        "/loans-drive-folder",
        "/pazomat-drive-folder",
        "/sibus-drive-folder",
        "/marketing-drive-folder",
    ],
)
def test_admin_and_drive_folder_endpoints_available(api_client, path):
    response = api_client.get(path, timeout=180.0)
    assert response.status_code < 500
