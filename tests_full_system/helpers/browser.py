from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from tests_full_system.settings import SETTINGS


def _storage_state_exists() -> bool:
    return Path(SETTINGS.browser_storage_state).exists()


@pytest.fixture(scope="session")
def playwright_manager():
    with sync_playwright() as manager:
        yield manager


@pytest.fixture(scope="session")
def browser(playwright_manager) -> Browser:
    browser_type = getattr(playwright_manager, SETTINGS.browser_name)
    browser = browser_type.launch(headless=SETTINGS.headless)
    yield browser
    browser.close()


@pytest.fixture
def browser_context(browser: Browser) -> BrowserContext:
    if not _storage_state_exists():
        pytest.skip(
            f"Browser storage state file not found: {SETTINGS.browser_storage_state}. "
            "Create one before running E2E tests."
        )
    context = browser.new_context(storage_state=SETTINGS.browser_storage_state)
    yield context
    context.close()


@pytest.fixture
def page(browser_context: BrowserContext) -> Page:
    page = browser_context.new_page()
    yield page
    page.close()
