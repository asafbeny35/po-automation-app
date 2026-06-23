from __future__ import annotations

import json
from urllib.parse import urlparse

from playwright.sync_api import Page

from tests_full_system.helpers.waits import wait_for_idle_ui, wait_for_visible
from tests_full_system.manifests.tabs import TOP_LEVEL_TABS
from tests_full_system.settings import SETTINGS


class AppShell:
    def __init__(self, page: Page) -> None:
        self.page = page

    def _is_local_base_url(self) -> bool:
        try:
            parsed = urlparse(SETTINGS.base_url)
        except Exception:
            return False
        return (parsed.hostname or "").strip().lower() in {"localhost", "127.0.0.1", "::1"}

    def _ensure_dev_auth(self) -> None:
        if not self._is_local_base_url():
            return
        response = self.page.context.request.post(
            f"{SETTINGS.base_url}/auth/dev-login",
            headers={
                "X-PO-Debug-Auth": "1",
                "Content-Type": "application/json",
            },
            data=json.dumps({"user_id": "asaf", "remember_me": True}),
        )
        if not response.ok:
            raise AssertionError(f"Dev auth failed: {response.status} {response.text()}")

    def open(self) -> None:
        self.page.goto(f"{SETTINGS.base_url}/", wait_until="domcontentloaded")
        wait_for_idle_ui(self.page)
        if self.page.locator(".top-tab").count() == 0:
            self._ensure_dev_auth()
            self.page.goto(f"{SETTINGS.base_url}/", wait_until="domcontentloaded")
            wait_for_idle_ui(self.page)

    def open_tab(self, tab_id: str) -> None:
        self.page.locator(f'.top-tab[data-tab="{tab_id}"]').click()
        wait_for_idle_ui(self.page)

    def assert_tab_key_surface_visible(self, tab_id: str) -> None:
        tab = next(item for item in TOP_LEVEL_TABS if item["tab_id"] == tab_id)
        selector = str(tab["key_selector"]).split(",")[0].strip()
        wait_for_visible(self.page, selector)

    def open_support_center(self) -> None:
        self.page.locator("#supportCenterFab").click()
        wait_for_visible(self.page, "#supportCenterModal")

    def close_support_center(self) -> None:
        self.page.locator("#supportCenterClose").click()
        wait_for_idle_ui(self.page)
