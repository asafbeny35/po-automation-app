from __future__ import annotations

from playwright.sync_api import Page


def wait_for_idle_ui(page: Page) -> None:
    page.wait_for_timeout(250)


def wait_for_visible(page: Page, selector: str, timeout: int = 10_000) -> None:
    page.locator(selector).first.wait_for(state="visible", timeout=timeout)
