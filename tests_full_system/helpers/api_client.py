from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import pyotp
import pytest

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
        self._auto_prod_auth_attempted = False
        if SETTINGS.api_session_cookie_value:
            self._set_session_cookie(
                SETTINGS.api_session_cookie_name,
                SETTINGS.api_session_cookie_value,
            )

    def close(self) -> None:
        self._client.close()

    def _cookie_domain(self) -> str | None:
        try:
            parsed = urlparse(self.base_url)
        except Exception:
            return None
        return (parsed.hostname or "").strip() or None

    def _set_session_cookie(self, name: str, value: str) -> None:
        domain = self._cookie_domain()
        if domain:
            self._client.cookies.set(name, value, domain=domain, path="/")
            return
        self._client.cookies.set(name, value)

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

    def ensure_prod_totp_auth(self) -> ApiResponse | None:
        if self._auto_prod_auth_attempted or self._is_local_base_url():
            return None
        self._auto_prod_auth_attempted = True
        auth_state_path = SETTINGS.project_root / "auth_state.json"
        if not auth_state_path.exists():
            return None
        try:
            auth_state = json.loads(auth_state_path.read_text(encoding="utf-8"))
            secret = str(auth_state.get("totp_secret") or "").strip()
            if not secret:
                return None
            code = pyotp.TOTP(secret).now()
            response = self._client.post(
                "/auth/totp/verify",
                json={"code": code, "remember_me": False},
            )
            if session_cookie := response.cookies.get(SETTINGS.api_session_cookie_name):
                self._set_session_cookie(SETTINGS.api_session_cookie_name, session_cookie)
            try:
                payload = response.json()
            except Exception:
                payload = response.text
            return ApiResponse(
                status_code=response.status_code,
                payload=payload,
                headers=dict(response.headers),
            )
        except Exception:
            return None

    def request(self, method: str, path: str, **kwargs: Any) -> ApiResponse:
        allow_unauthenticated = bool(kwargs.pop("allow_unauthenticated", False))
        # Allow per-call timeout override without mutating the shared client
        if "timeout" not in kwargs:
            kwargs["timeout"] = SETTINGS.request_timeout_seconds
        self.ensure_dev_auth()
        response = self._client.request(method.upper(), path, **kwargs)
        if response.status_code == 401 and not self._is_local_base_url():
            self.ensure_prod_totp_auth()
            response = self._client.request(method.upper(), path, **kwargs)
        if (
            response.status_code == 401
            and not self._is_local_base_url()
            and not allow_unauthenticated
            and not path.startswith("/auth/")
        ):
            pytest.skip(f"{path} requires authenticated production session")
        if session_cookie := response.cookies.get(SETTINGS.api_session_cookie_name):
            self._set_session_cookie(SETTINGS.api_session_cookie_name, session_cookie)
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
