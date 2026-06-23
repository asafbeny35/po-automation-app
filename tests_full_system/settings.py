from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestSettings:
    project_root: Path
    base_url: str
    sandbox_mode: str
    allow_prod_creation: bool
    whatsapp_test_number: str
    browser_name: str
    headless: bool
    browser_storage_state: str
    api_session_cookie_name: str
    api_session_cookie_value: str
    request_timeout_seconds: float
    screenshot_dir: Path
    artifacts_dir: Path
    visible_test_tag: str
    visible_test_name_base: str


def load_settings() -> TestSettings:
    project_root = Path(__file__).resolve().parents[1]
    base_url = os.getenv("PO_TEST_BASE_URL", "http://localhost:8000").rstrip("/")
    browser_storage_state = os.getenv(
        "PO_TEST_BROWSER_STORAGE_STATE",
        str(project_root / "tests_full_system" / "artifacts" / "browser-storage-state.json"),
    )
    return TestSettings(
        project_root=project_root,
        base_url=base_url,
        sandbox_mode=os.getenv("PO_TEST_GREENINVOICE_MODE", "sandbox"),
        allow_prod_creation=os.getenv("PO_TEST_ALLOW_PROD", "false").strip().lower() == "true",
        whatsapp_test_number=os.getenv("PO_TEST_WHATSAPP_NUMBER", "0547720142"),
        browser_name=os.getenv("PO_TEST_BROWSER", "chromium"),
        headless=os.getenv("PO_TEST_HEADLESS", "true").strip().lower() == "true",
        browser_storage_state=browser_storage_state,
        api_session_cookie_name=os.getenv("PO_TEST_SESSION_COOKIE_NAME", "session"),
        api_session_cookie_value=os.getenv("PO_TEST_SESSION_COOKIE_VALUE", ""),
        request_timeout_seconds=float(os.getenv("PO_TEST_REQUEST_TIMEOUT", "30")),
        screenshot_dir=project_root / "tests_full_system" / "artifacts" / "screenshots",
        artifacts_dir=project_root / "tests_full_system" / "artifacts",
        visible_test_tag=os.getenv("PO_TEST_VISIBLE_TAG", "TEST"),
        visible_test_name_base=os.getenv("PO_TEST_VISIBLE_NAME_BASE", "נעלולי פלא"),
    )


SETTINGS = load_settings()
