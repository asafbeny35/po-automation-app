from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import io
import ipaddress
import json
import os
import secrets
import smtplib
import ssl
import subprocess
import time
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path
from typing import Any

import pyotp
import qrcode
from starlette.requests import Request
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import options_to_json
from webauthn.helpers.structs import PublicKeyCredentialDescriptor, UserVerificationRequirement
from . import supabase_store
from .config import settings
from .gmail_oauth import gmail_connection_status, gmail_oauth_send_status, send_mail_via_gmail_api


AUTH_COOKIE_NAME = "po_auth"
DEFAULT_PRIMARY_USER_ID = "asaf"
DEFAULT_SECONDARY_USER_ID = "mom"
DEFAULT_PRIMARY_EMAIL_ADDRESS = "asafbeny@gmail.com"
DEFAULT_SECONDARY_EMAIL_ADDRESS = "malibeny1@gmail.com"
DEFAULT_PRIMARY_TOTP_SECRET = "Y5KORRGYX7SOFWEHGGD5D2RZJ66W5AOZ"
DEFAULT_PRIMARY_PASSKEYS = [
    {
        "id": "WYuLHRZRPSy0yjF1r_zXFQ",
        "public_key": "pQECAyYgASFYIHJBXqNKQ3SU4EYS0TD6p5LMuKLD9tEQAaDq2Mwby13qIlggnP-L5x1oEjesn-Cxlt6OcxTq3VAnfnMs66GoJ2b71mk",
        "sign_count": 0,
        "created_at": 1776459011,
    }
]
_AUTH_STATE_CACHE: dict[str, Any] | None = None
_AUTH_STATE_CACHE_MTIME_NS: int | None = None
_AUTH_STATE_DOMAIN = "app_auth_state"


def _auth_state_path() -> Path:
    override = str(os.getenv("PO_AUTH_STATE_PATH", "") or "").strip()
    if override:
        return Path(override)
    if str(os.getenv("VERCEL", "") or "").strip() == "1":
        return Path("/tmp/auth_state.json")
    return Path(__file__).resolve().parents[1] / "auth_state.json"


AUTH_STATE_PATH = _auth_state_path()


def _supabase_auth_state_enabled() -> bool:
    return supabase_store.is_enabled() and supabase_store.supports_domain(_AUTH_STATE_DOMAIN)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


def _default_user(
    user_id: str,
    *,
    display_name: str,
    username: str,
    email_address: str = "",
) -> dict[str, Any]:
    return {
        "id": user_id,
        "display_name": display_name,
        "username": username,
        "email_address": email_address,
        "webauthn_user_id": _b64url_encode(secrets.token_bytes(32)),
        "totp_secret": "",
        "passkeys": [],
        "email_enabled": False,
        "totp_enabled": False,
        "passkey_enabled": False,
        "updated_at": int(time.time()),
    }


def _default_state() -> dict[str, Any]:
    state = {
        "cookie_secret": _b64url_encode(secrets.token_bytes(32)),
        "default_user_id": DEFAULT_PRIMARY_USER_ID,
        "users": {
            DEFAULT_PRIMARY_USER_ID: _default_user(
                DEFAULT_PRIMARY_USER_ID,
                display_name="אסף",
                username="asafbeny",
                email_address=DEFAULT_PRIMARY_EMAIL_ADDRESS,
            ),
            DEFAULT_SECONDARY_USER_ID: _default_user(
                DEFAULT_SECONDARY_USER_ID,
                display_name="אמא",
                username="mom",
                email_address=DEFAULT_SECONDARY_EMAIL_ADDRESS,
            ),
        },
        "updated_at": int(time.time()),
    }
    primary = state["users"][DEFAULT_PRIMARY_USER_ID]
    primary["totp_secret"] = DEFAULT_PRIMARY_TOTP_SECRET
    primary["passkeys"] = copy.deepcopy(DEFAULT_PRIMARY_PASSKEYS)
    primary["email_enabled"] = True
    primary["totp_enabled"] = True
    primary["passkey_enabled"] = True
    return state


_DEFAULT_USER_EMAILS: dict[str, str] = {
    DEFAULT_PRIMARY_USER_ID: DEFAULT_PRIMARY_EMAIL_ADDRESS,
    DEFAULT_SECONDARY_USER_ID: DEFAULT_SECONDARY_EMAIL_ADDRESS,
}


def _normalize_user_entry(user_id: str, raw: Any) -> dict[str, Any]:
    defaults = _default_user(
        user_id,
        display_name="אסף" if user_id == DEFAULT_PRIMARY_USER_ID else ("אמא" if user_id == DEFAULT_SECONDARY_USER_ID else user_id),
        username="asafbeny" if user_id == DEFAULT_PRIMARY_USER_ID else ("mom" if user_id == DEFAULT_SECONDARY_USER_ID else user_id),
        email_address=_DEFAULT_USER_EMAILS.get(user_id, ""),
    )
    entry = dict(defaults)
    if isinstance(raw, dict):
        entry.update(raw)
    entry["id"] = user_id
    if not str(entry.get("display_name") or "").strip():
        entry["display_name"] = defaults["display_name"]
    if not str(entry.get("username") or "").strip():
        entry["username"] = defaults["username"]
    if not str(entry.get("webauthn_user_id") or "").strip():
        entry["webauthn_user_id"] = defaults["webauthn_user_id"]
    if not isinstance(entry.get("passkeys"), list):
        entry["passkeys"] = []
    # Backfill email if empty but a known default exists
    if not str(entry.get("email_address") or "").strip():
        default_email = _DEFAULT_USER_EMAILS.get(user_id, "")
        if default_email:
            entry["email_address"] = default_email
            entry["email_enabled"] = True
    return entry


def _migrate_legacy_state(raw: dict[str, Any] | None) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    state = _default_state()
    state.update({k: v for k, v in raw.items() if k not in {"users", "default_user_id"}})

    users_raw = raw.get("users")
    if isinstance(users_raw, dict) and users_raw:
        users = {
            user_id: _normalize_user_entry(str(user_id).strip() or user_id, value)
            for user_id, value in users_raw.items()
        }
    else:
        primary = _default_user(
            DEFAULT_PRIMARY_USER_ID,
            display_name="אסף",
            username="asafbeny",
            email_address=str(raw.get("email_address") or "").strip(),
        )
        primary.update(
            {
                "webauthn_user_id": str(raw.get("webauthn_user_id") or primary["webauthn_user_id"]).strip(),
                "totp_secret": str(raw.get("totp_secret") or "").strip(),
                "passkeys": raw.get("passkeys") if isinstance(raw.get("passkeys"), list) else [],
                "email_enabled": bool(raw.get("email_enabled")),
                "totp_enabled": bool(raw.get("totp_enabled")),
                "passkey_enabled": bool(raw.get("passkey_enabled")),
            }
        )
        users = {
            DEFAULT_PRIMARY_USER_ID: _normalize_user_entry(DEFAULT_PRIMARY_USER_ID, primary),
            DEFAULT_SECONDARY_USER_ID: _normalize_user_entry(
                DEFAULT_SECONDARY_USER_ID,
                _default_user(DEFAULT_SECONDARY_USER_ID, display_name="אמא", username="mom"),
            ),
        }

    if DEFAULT_PRIMARY_USER_ID not in users:
        users[DEFAULT_PRIMARY_USER_ID] = _normalize_user_entry(DEFAULT_PRIMARY_USER_ID, {})
    if DEFAULT_SECONDARY_USER_ID not in users:
        users[DEFAULT_SECONDARY_USER_ID] = _normalize_user_entry(DEFAULT_SECONDARY_USER_ID, {})

    state["users"] = users
    default_user_id = str(raw.get("default_user_id") or state.get("default_user_id") or DEFAULT_PRIMARY_USER_ID).strip() or DEFAULT_PRIMARY_USER_ID
    state["default_user_id"] = default_user_id if default_user_id in users else DEFAULT_PRIMARY_USER_ID
    return state


def list_auth_users(state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    state = state or load_auth_state()
    users = state.get("users") or {}
    return [users[user_id] for user_id in users if isinstance(users.get(user_id), dict)]


def get_auth_user(state: dict[str, Any] | None, user_id: str | None = None) -> dict[str, Any]:
    state = state or load_auth_state()
    users = state.get("users") or {}
    target_user_id = str(user_id or state.get("default_user_id") or DEFAULT_PRIMARY_USER_ID).strip() or DEFAULT_PRIMARY_USER_ID
    user = users.get(target_user_id)
    if isinstance(user, dict):
        return user
    fallback = users.get(DEFAULT_PRIMARY_USER_ID)
    if isinstance(fallback, dict):
        return fallback
    first_key = next(iter(users), DEFAULT_PRIMARY_USER_ID)
    return _normalize_user_entry(first_key, users.get(first_key))


def _read_local_auth_state_raw() -> dict[str, Any]:
    candidate_paths = [AUTH_STATE_PATH]
    bundled_repo_path = Path(__file__).resolve().parents[1] / "auth_state.json"
    if bundled_repo_path not in candidate_paths:
        candidate_paths.append(bundled_repo_path)
    for path in candidate_paths:
        if not path.exists():
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            raw = {}
        if isinstance(raw, dict) and raw:
            return raw
    return {}


def _state_has_enabled_method(state: dict[str, Any] | None) -> bool:
    users = (state or {}).get("users") or {}
    for user in users.values():
        if not isinstance(user, dict):
            continue
        if bool(user.get("email_enabled") and user.get("email_address")):
            return True
        if bool(user.get("totp_enabled") and user.get("totp_secret")):
            return True
        if bool(user.get("passkey_enabled") and user.get("passkeys")):
            return True
    return False


def load_auth_state() -> dict[str, Any]:
    global _AUTH_STATE_CACHE, _AUTH_STATE_CACHE_MTIME_NS
    if _supabase_auth_state_enabled():
        if _AUTH_STATE_CACHE is not None:
            return copy.deepcopy(_AUTH_STATE_CACHE)
        try:
            rows = supabase_store.fetch_domain_rows(_AUTH_STATE_DOMAIN)
        except Exception:
            rows = []
        raw = rows[0] if rows and isinstance(rows[0], dict) else {}
        state = _migrate_legacy_state(raw)
        local_raw = _read_local_auth_state_raw()
        local_state = _migrate_legacy_state(local_raw) if local_raw else {}
        if (not raw or not _state_has_enabled_method(state)) and local_state and _state_has_enabled_method(local_state):
            state = copy.deepcopy(local_state)
            save_auth_state(state)
            return copy.deepcopy(state)
        if not _state_has_enabled_method(state):
            state = _default_state()
            save_auth_state(state)
            return copy.deepcopy(state)
        if not state.get("cookie_secret"):
            state["cookie_secret"] = _default_state()["cookie_secret"]
        if not raw:
            save_auth_state(state)
            return copy.deepcopy(state)
        _AUTH_STATE_CACHE = copy.deepcopy(state)
        _AUTH_STATE_CACHE_MTIME_NS = None
        return copy.deepcopy(state)
    if not AUTH_STATE_PATH.exists():
        state = _default_state()
        save_auth_state(state)
        return copy.deepcopy(state)
    try:
        current_mtime_ns = AUTH_STATE_PATH.stat().st_mtime_ns
    except Exception:
        current_mtime_ns = None
    if (
        _AUTH_STATE_CACHE is not None
        and _AUTH_STATE_CACHE_MTIME_NS is not None
        and current_mtime_ns is not None
        and _AUTH_STATE_CACHE_MTIME_NS == current_mtime_ns
    ):
        return copy.deepcopy(_AUTH_STATE_CACHE)
    raw_dict = _read_local_auth_state_raw()
    state = _migrate_legacy_state(raw_dict)
    if not state.get("cookie_secret"):
        state["cookie_secret"] = _default_state()["cookie_secret"]
    if state != raw_dict:
        save_auth_state(state)
        return copy.deepcopy(state)
    _AUTH_STATE_CACHE = copy.deepcopy(state)
    _AUTH_STATE_CACHE_MTIME_NS = current_mtime_ns
    return copy.deepcopy(state)


def save_auth_state(state: dict[str, Any]) -> None:
    global _AUTH_STATE_CACHE, _AUTH_STATE_CACHE_MTIME_NS
    state = _migrate_legacy_state(dict(state or {}))
    state["updated_at"] = int(time.time())
    if _supabase_auth_state_enabled():
        supabase_store.replace_domain_rows(_AUTH_STATE_DOMAIN, [state])
        _AUTH_STATE_CACHE_MTIME_NS = None
        _AUTH_STATE_CACHE = copy.deepcopy(state)
        return
    AUTH_STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        AUTH_STATE_PATH.chmod(0o600)
    except Exception:
        pass
    try:
        _AUTH_STATE_CACHE_MTIME_NS = AUTH_STATE_PATH.stat().st_mtime_ns
    except Exception:
        _AUTH_STATE_CACHE_MTIME_NS = None
    _AUTH_STATE_CACHE = copy.deepcopy(state)


def get_enabled_methods(state: dict[str, Any] | None = None, user_id: str | None = None) -> dict[str, bool]:
    user = get_auth_user(state, user_id)
    return {
        "email": bool(user.get("email_enabled") and user.get("email_address")),
        "totp": bool(user.get("totp_enabled") and user.get("totp_secret")),
        "passkey": bool(user.get("passkey_enabled") and user.get("passkeys")),
    }


def has_any_enabled_method(state: dict[str, Any] | None = None, user_id: str | None = None) -> bool:
    methods = get_enabled_methods(state, user_id)
    return any(methods.values())


def issue_auth_token(secret_b64: str, remember_me: bool, user_id: str) -> str:
    now = int(time.time())
    exp = now + (30 * 24 * 60 * 60 if remember_me else 12 * 60 * 60)
    payload = {"sub": str(user_id or DEFAULT_PRIMARY_USER_ID), "iat": now, "exp": exp, "remember": bool(remember_me), "nonce": secrets.token_hex(8)}
    body = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64url_encode(hmac.new(_b64url_decode(secret_b64), body.encode("utf-8"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def verify_auth_token(token: str, secret_b64: str) -> dict[str, Any] | None:
    try:
        body, signature = token.split(".", 1)
        expected = _b64url_encode(hmac.new(_b64url_decode(secret_b64), body.encode("utf-8"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            return None
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
        if int(payload.get("exp", 0)) < int(time.time()):
            return None
        return payload
    except Exception:
        return None


def is_request_authenticated(request: Request) -> bool:
    if _debug_authenticated_user_id(request):
        return True
    token = request.cookies.get(AUTH_COOKIE_NAME, "")
    if not token:
        return False
    state = load_auth_state()
    return verify_auth_token(token, state["cookie_secret"]) is not None


def authenticated_user_id(request: Request) -> str | None:
    debug_user_id = _debug_authenticated_user_id(request)
    if debug_user_id:
        return debug_user_id
    token = request.cookies.get(AUTH_COOKIE_NAME, "")
    if not token:
        return None
    state = load_auth_state()
    payload = verify_auth_token(token, state["cookie_secret"])
    if not payload:
        return None
    user_id = str(payload.get("sub") or "").strip()
    return user_id or None


def _debug_private_hostname(value: str) -> bool:
    host = str(value or "").strip().lower()
    if host in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        parsed = ipaddress.ip_address(host)
        return parsed.is_private or parsed.is_loopback
    except ValueError:
        return host.endswith(".local")


def _debug_authenticated_user_id(request: Request) -> str | None:
    allow_private_debug_auth = str(os.getenv("PO_ALLOW_PRIVATE_DEBUG_AUTH") or "").strip().lower() in {"1", "true", "yes", "on"}
    if not allow_private_debug_auth:
        return None
    debug_header = str(request.headers.get("x-po-debug-auth") or "").strip().lower()
    if debug_header not in {"1", "true", "yes", "debug"}:
        return None
    host = str(request.url.hostname or "").strip().lower()
    if not _debug_private_hostname(host):
        return None
    requested_user_id = str(request.headers.get("x-po-debug-user") or "").strip() or DEFAULT_PRIMARY_USER_ID
    return requested_user_id


def auth_cookie_settings(remember_me: bool) -> dict[str, Any]:
    settings: dict[str, Any] = {
        "httponly": True,
        "samesite": "lax",
        "secure": False,
        "path": "/",
    }
    if remember_me:
        settings["max_age"] = 30 * 24 * 60 * 60
    return settings


def clear_auth_cookie(response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")


def build_qr_data_uri(uri: str) -> str:
    image = qrcode.make(uri)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def build_totp_setup_payload(state: dict[str, Any], user_id: str | None = None, app_name: str = "PO Automation") -> dict[str, str]:
    user = get_auth_user(state, user_id)
    secret = str(user.get("totp_secret") or "").strip()
    if not secret:
        secret = pyotp.random_base32()
        user["totp_secret"] = secret
        save_auth_state(state)
    email_label = str(user.get("email_address") or user.get("display_name") or "local-user").strip() or "local-user"
    uri = pyotp.TOTP(secret).provisioning_uri(name=email_label, issuer_name=app_name)
    return {"secret": secret, "uri": uri, "qr_data_uri": build_qr_data_uri(uri)}


def _normalize_totp_code(code: str | None) -> str:
    raw = str(code or "").strip()
    return "".join(ch for ch in raw if ch.isdigit())


def resolve_totp_user(state: dict[str, Any], code: str, user_id: str | None = None) -> dict[str, Any] | None:
    normalized_code = _normalize_totp_code(code)
    if not normalized_code:
        return None

    requested_user = get_auth_user(state, user_id)
    requested_user_id = str(requested_user.get("id") or "").strip()
    candidate_users: list[dict[str, Any]] = []
    if requested_user_id:
        candidate_users.append(requested_user)

    for candidate in list_auth_users(state):
        candidate_id = str(candidate.get("id") or "").strip()
        if not candidate_id or candidate_id == requested_user_id:
            continue
        candidate_users.append(candidate)

    for candidate in candidate_users:
        if not bool(candidate.get("totp_enabled")):
            continue
        secret = str(candidate.get("totp_secret") or "").strip()
        if not secret:
            continue
        if pyotp.TOTP(secret).verify(normalized_code, valid_window=2):
            return candidate
    return None


def verify_totp_code(state: dict[str, Any], code: str, user_id: str | None = None) -> bool:
    return resolve_totp_user(state, code, user_id) is not None


def send_email_code_via_mail_app(email_address: str, code: str) -> None:
    subject = "קוד התחברות ל-PO Automation"
    body = f"הקוד שלך לכניסה לאפליקציה הוא: {code}\n\nהקוד תקף ל-10 דקות."
    html_body = (
        "<div dir='rtl' style='font-family:Arial,sans-serif;font-size:15px;line-height:1.8;'>"
        f"<p>הקוד שלך לכניסה לאפליקציה הוא: <strong>{code}</strong></p>"
        "<p>הקוד תקף ל-10 דקות.</p>"
        "</div>"
    )
    smtp_from_email = str(settings.smtp_from_email or "office@ben-yacov.com").strip() or "office@ben-yacov.com"
    smtp_from_name = str(settings.smtp_from_name or "בן יעקב פתרונות טקסטיל").strip() or "בן יעקב פתרונות טקסטיל"

    gmail_status = gmail_connection_status()
    if gmail_status.get("can_send"):
        send_mail_via_gmail_api(
            [email_address],
            subject,
            body,
            html_body,
            [],
            sender_address=smtp_from_email,
            sender_name=smtp_from_name,
        )
        return

    gmail_send_status = gmail_oauth_send_status()
    if gmail_send_status == "revoked_or_expired":
        raise RuntimeError("טוקן Gmail OAuth של office@ben-yacov.com פג או בוטל. צריך להיכנס ל־/gmail-oauth/start ולחבר מחדש את Gmail.")
    if gmail_status.get("token_present") and gmail_send_status == "missing_scope":
        raise RuntimeError("Gmail OAuth מחובר בלי הרשאת שליחה. צריך לחבר מחדש את Gmail עם scope של gmail.send.")
    if gmail_status.get("oauth_ready"):
        raise RuntimeError("Gmail OAuth מחובר, אבל אין כרגע הרשאת שליחה. צריך לחבר מחדש את Gmail ולא לחזור ל-SMTP.")

    smtp_host = str(settings.smtp_host or "").strip()
    smtp_user = str(settings.smtp_username or "").strip()
    smtp_password = str(settings.smtp_password or "").strip()
    if smtp_host and smtp_user and smtp_password:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((smtp_from_name, smtp_from_email))
        msg["To"] = email_address
        msg.set_content(body)
        msg.add_alternative(html_body, subtype="html")
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(smtp_host, settings.smtp_port, context=ssl.create_default_context()) as server:
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, settings.smtp_port) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(smtp_user, smtp_password)
                server.send_message(msg)
        return

    if os.getenv("VERCEL", "").strip() == "1":
        raise RuntimeError("לא הוגדר חיבור backend תקין לשליחת קוד במייל. צריך לחבר Gmail OAuth עם הרשאת שליחה או SMTP עבור office@ben-yacov.com.")

    script = """
on run argv
  set recipientAddress to item 1 of argv
  set messageSubject to item 2 of argv
  set messageBody to item 3 of argv
  tell application "Mail"
    set newMessage to make new outgoing message with properties {visible:false, subject:messageSubject, content:messageBody & return & return}
    tell newMessage
      make new to recipient at end of to recipients with properties {address:recipientAddress}
      send
    end tell
  end tell
end run
"""
    subprocess.run(["osascript", "-e", script, email_address, subject, body], check=True)


def webauthn_rp_id_for_request(request: Request) -> str:
    host = (request.url.hostname or "localhost").strip().lower()
    return "localhost" if host in {"127.0.0.1", "::1"} else host


def webauthn_origin_for_request(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


def generate_passkey_registration_options(request: Request, state: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    user = get_auth_user(state, user_id)
    rp_id = webauthn_rp_id_for_request(request)
    challenge = secrets.token_bytes(32)
    request.session["passkey_registration_challenge"] = _b64url_encode(challenge)
    request.session["passkey_registration_origin"] = webauthn_origin_for_request(request)
    request.session["passkey_registration_rp_id"] = rp_id
    request.session["passkey_registration_user_id"] = str(user.get("id") or DEFAULT_PRIMARY_USER_ID)
    exclude = []
    for item in user.get("passkeys") or []:
        credential_id = str(item.get("id") or "").strip()
        if credential_id:
            exclude.append(PublicKeyCredentialDescriptor(id=_b64url_decode(credential_id)))
    options = generate_registration_options(
        rp_id=rp_id,
        rp_name="PO Automation",
        user_id=_b64url_decode(str(user["webauthn_user_id"])),
        user_name=str(user.get("username") or user.get("id") or "user"),
        user_display_name=str(user.get("display_name") or "PO Automation"),
        challenge=challenge,
        exclude_credentials=exclude or None,
    )
    return json.loads(options_to_json(options))


def complete_passkey_registration(request: Request, state: dict[str, Any], credential: dict[str, Any]) -> dict[str, Any]:
    user = get_auth_user(state, request.session.get("passkey_registration_user_id"))
    challenge_b64 = request.session.get("passkey_registration_challenge", "")
    expected_origin = request.session.get("passkey_registration_origin") or webauthn_origin_for_request(request)
    expected_rp_id = request.session.get("passkey_registration_rp_id") or webauthn_rp_id_for_request(request)
    verification = verify_registration_response(
        credential=credential,
        expected_challenge=_b64url_decode(challenge_b64),
        expected_origin=expected_origin,
        expected_rp_id=expected_rp_id,
        require_user_verification=True,
    )
    credential_id = _b64url_encode(verification.credential_id)
    existing = [item for item in (user.get("passkeys") or []) if str(item.get("id")) != credential_id]
    existing.append(
        {
            "id": credential_id,
            "public_key": _b64url_encode(verification.credential_public_key),
            "sign_count": int(verification.sign_count or 0),
            "created_at": int(time.time()),
        }
    )
    user["passkeys"] = existing
    user["passkey_enabled"] = True
    save_auth_state(state)
    request.session.pop("passkey_registration_challenge", None)
    request.session.pop("passkey_registration_user_id", None)
    return {"id": credential_id}


def generate_passkey_authentication_options(request: Request, state: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    user = get_auth_user(state, user_id)
    rp_id = webauthn_rp_id_for_request(request)
    challenge = secrets.token_bytes(32)
    request.session["passkey_login_challenge"] = _b64url_encode(challenge)
    request.session["passkey_login_origin"] = webauthn_origin_for_request(request)
    request.session["passkey_login_rp_id"] = rp_id
    request.session["passkey_login_user_id"] = str(user.get("id") or DEFAULT_PRIMARY_USER_ID)
    allow = []
    for item in user.get("passkeys") or []:
        credential_id = str(item.get("id") or "").strip()
        if credential_id:
            allow.append(PublicKeyCredentialDescriptor(id=_b64url_decode(credential_id)))
    options = generate_authentication_options(
        rp_id=rp_id,
        challenge=challenge,
        allow_credentials=allow or None,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    return json.loads(options_to_json(options))


def complete_passkey_authentication(request: Request, state: dict[str, Any], credential: dict[str, Any]) -> dict[str, Any]:
    user = get_auth_user(state, request.session.get("passkey_login_user_id"))
    credential_id = str(credential.get("id") or "").strip()
    known = next((item for item in (user.get("passkeys") or []) if str(item.get("id") or "") == credential_id), None)
    if not known:
        raise ValueError("Passkey לא מוכר.")
    challenge_b64 = request.session.get("passkey_login_challenge", "")
    expected_origin = request.session.get("passkey_login_origin") or webauthn_origin_for_request(request)
    expected_rp_id = request.session.get("passkey_login_rp_id") or webauthn_rp_id_for_request(request)
    verification = verify_authentication_response(
        credential=credential,
        expected_challenge=_b64url_decode(challenge_b64),
        expected_origin=expected_origin,
        expected_rp_id=expected_rp_id,
        credential_public_key=_b64url_decode(str(known.get("public_key") or "")),
        credential_current_sign_count=int(known.get("sign_count") or 0),
        require_user_verification=True,
    )
    known["sign_count"] = int(verification.new_sign_count or known.get("sign_count") or 0)
    save_auth_state(state)
    request.session.pop("passkey_login_challenge", None)
    request.session.pop("passkey_login_user_id", None)
    return known
