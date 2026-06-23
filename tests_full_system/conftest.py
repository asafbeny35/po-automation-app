from __future__ import annotations

import os
from pathlib import Path

import pytest

from tests_full_system.helpers.api_client import ApiClient
from tests_full_system.settings import SETTINGS


def pytest_configure(config: pytest.Config) -> None:
    SETTINGS.screenshot_dir.mkdir(parents=True, exist_ok=True)
    SETTINGS.artifacts_dir.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="session")
def settings():
    return SETTINGS


@pytest.fixture(scope="session")
def api_client() -> ApiClient:
    client = ApiClient()
    yield client
    client.close()


@pytest.fixture(scope="session")
def project_root() -> Path:
    return SETTINGS.project_root


@pytest.fixture(scope="session")
def ensure_sandbox_guard():
    if SETTINGS.allow_prod_creation:
        pytest.fail("PO_TEST_ALLOW_PROD=true is forbidden for this suite by default.")
    if SETTINGS.sandbox_mode.strip().lower() != "sandbox":
        pytest.fail(f"Expected sandbox mode for test execution, got: {SETTINGS.sandbox_mode!r}")
    return True


@pytest.fixture
def test_entity_marker() -> str:
    return f"{SETTINGS.visible_test_tag} | {SETTINGS.visible_test_name_base}"


@pytest.fixture(scope="session")
def environment_snapshot() -> dict[str, str]:
    keys = [
        "PO_TEST_BASE_URL",
        "PO_TEST_GREENINVOICE_MODE",
        "PO_TEST_ALLOW_PROD",
        "PO_TEST_WHATSAPP_NUMBER",
        "PO_TEST_BROWSER",
        "PO_TEST_HEADLESS",
        "PO_TEST_BROWSER_STORAGE_STATE",
        "PO_TEST_SESSION_COOKIE_NAME",
    ]
    return {key: os.getenv(key, "") for key in keys}
