"""Toast assertion helpers.

showToast(type, title, message) adds a div.toast.{type} containing
<strong>{title}</strong><span>{message}</span> to #toastStack.
"""
from __future__ import annotations

from playwright.sync_api import Page


def wait_for_toast(
    page: Page,
    *,
    type: str,  # "success" | "error" | "info"
    title_contains: str | None = None,
    timeout: int = 6_000,
) -> None:
    """Wait for a toast of the given type, optionally matching the title text."""
    selector = f".toast.{type}.visible"
    page.locator(selector).first.wait_for(state="visible", timeout=timeout)
    if title_contains:
        loc = page.locator(f".toast.{type}.visible strong")
        loc.filter(has_text=title_contains).first.wait_for(state="visible", timeout=timeout)


def wait_for_error_toast(page: Page, title_contains: str | None = None, timeout: int = 6_000) -> None:
    wait_for_toast(page, type="error", title_contains=title_contains, timeout=timeout)


def wait_for_success_toast(page: Page, title_contains: str | None = None, timeout: int = 6_000) -> None:
    wait_for_toast(page, type="success", title_contains=title_contains, timeout=timeout)


def wait_for_info_toast(page: Page, title_contains: str | None = None, timeout: int = 6_000) -> None:
    wait_for_toast(page, type="info", title_contains=title_contains, timeout=timeout)


def assert_no_toast(page: Page, timeout: int = 800) -> None:
    """Assert that no toast appears within the timeout window."""
    count = page.locator(".toast.visible").count()
    assert count == 0, f"Expected no toast but found {count} visible toast(s)"
