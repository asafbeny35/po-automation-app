from __future__ import annotations

import base64
import json
from pathlib import Path

from google.oauth2.service_account import Credentials

from .config import settings
from .runtime_paths import PROJECT_ROOT


def _configured_value() -> str:
    return str(settings.google_service_account_json or "").strip()


def _local_fallback_path() -> Path:
    return PROJECT_ROOT / "google-credentials.json"


def _parse_inline_credentials(raw: str) -> dict | None:
    value = str(raw or "").strip()
    if not value:
        return None
    try:
        if value.startswith("{"):
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else None
    except Exception:
        pass
    try:
        decoded = base64.b64decode(value).decode("utf-8")
        parsed = json.loads(decoded)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        return None


def resolve_service_account_source() -> tuple[str, str | Path | dict]:
    configured = _configured_value()
    if configured:
        inline = _parse_inline_credentials(configured)
        if inline:
            return "info", inline
        try:
            configured_path = Path(configured)
            if configured_path.exists():
                return "file", configured_path
        except OSError:
            pass
    local_fallback = _local_fallback_path()
    if local_fallback.exists():
        return "file", local_fallback
    raise FileNotFoundError("לא הוגדר GOOGLE_SERVICE_ACCOUNT_JSON ולא נמצא google-credentials.json מקומי.")


def build_service_account_credentials(scopes: list[str] | tuple[str, ...]) -> Credentials:
    source_kind, payload = resolve_service_account_source()
    if source_kind == "info":
        return Credentials.from_service_account_info(payload, scopes=scopes)
    return Credentials.from_service_account_file(str(payload), scopes=scopes)
