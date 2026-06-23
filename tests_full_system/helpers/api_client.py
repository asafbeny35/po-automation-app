from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from tests_full_system.settings import SETTINGS


@dataclass
class ApiResponse:
    status_code: int
    payload: Any
    headers: dict[str, str]


class ApiClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or SETTINGS.base_url).rstrip("/")
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=SETTINGS.request_timeout_seconds,
            follow_redirects=False,
        )
        self._auto_auth_attempted = False
        if SETTINGS.api_session_cookie_value:
            self._client.cookies.set(
                SETTINGS.api_session_cookie_name,
                SETTINGS.api_session_cookie_value,
            )

    def close(self) -> None:
        self._client.close()

    def _is_local_base_url(self) -> bool:
        try:
            parsed = urlparse(self.base_url)
        except Exception:
            return False
        hostname = (parsed.hostname or "").strip().lower()
        return hostname in {"localhost", "127.0.0.1", "::1"}

    def ensure_dev_auth(self) -> ApiResponse | None:
        if self._auto_auth_attempted:
            return None
        self._auto_auth_attempted = True
        if not self._is_local_base_url():
            return None
        response = self._client.post(
            "/auth/dev-login",
            headers={"X-PO-Debug-Auth": "1"},
            json={"user_id": "asaf", "remember_me": True},
        )
        try:
            payload = response.json()
        except Exception:
            payload = response.text
        return ApiResponse(
            status_code=response.status_code,
            payload=payload,
            headers=dict(response.headers),
        )

    def request(self, method: str, path: str, **kwargs: Any) -> ApiResponse:
        self.ensure_dev_auth()
        response = self._client.request(method.upper(), path, **kwargs)
        try:
            payload = response.json()
        except Exception:
            payload = response.text
        return ApiResponse(
            status_code=response.status_code,
            payload=payload,
            headers=dict(response.headers),
        )

    def get(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> ApiResponse:
        return self.request("POST", path, **kwargs)
