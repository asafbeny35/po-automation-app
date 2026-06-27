from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests_full_system.helpers.api_client import ApiClient
from tests_full_system.settings import SETTINGS


def _is_local_base_url() -> bool:
    base_url = (SETTINGS.base_url or "").strip().lower()
    return base_url.startswith("http://localhost") or base_url.startswith("http://127.0.0.1")


def pytest_configure(config: pytest.Config) -> None:
    SETTINGS.screenshot_dir.mkdir(parents=True, exist_ok=True)
    SETTINGS.artifacts_dir.mkdir(parents=True, exist_ok=True)
    config.addinivalue_line("markers", "localhost_only: test is valid only against localhost/dev-login flow")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if _is_local_base_url():
        return
    skip_localhost_only = pytest.mark.skip(reason="localhost-only test skipped on production/staging base URL")
    for item in items:
        if item.get_closest_marker("localhost_only"):
            item.add_marker(skip_localhost_only)


@pytest.fixture(scope="session")
def settings():
    return SETTINGS


@pytest.fixture
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


@pytest.fixture(scope="session", autouse=True)
def auto_cleanup_after_session():
    """Automatically delete all test-created data after every test session."""
    yield
    # Skip cleanup if explicitly disabled
    if os.getenv("PO_TEST_SKIP_CLEANUP", "").strip().lower() in {"1", "true", "yes"}:
        return
    try:
        from tests_full_system.run_cleanup import run_cleanup
        report = run_cleanup(apply=True, include_drive=True, include_local=True, include_sheets=True)
        has_work = any(d["matched_rows"] > 0 for d in report.datasets)
        if has_work or report.drive["files_deleted"] or report.drive["folders_deleted"]:
            print("\n[cleanup] Test data removed:")
            print(json.dumps({"datasets": report.datasets, "drive": report.drive}, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(f"\n[cleanup] WARNING: cleanup failed — {exc}")


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
