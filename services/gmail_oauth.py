from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
import time
from email.message import EmailMessage
from email.utils import format_datetime, formataddr, getaddresses, parsedate_to_datetime
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from .config import settings
from . import supabase_store
from .runtime_paths import runtime_root


GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
GMAIL_READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SCOPES = [
    GMAIL_SEND_SCOPE,
    GMAIL_READ_SCOPE,
]
_GMAIL_OAUTH_TOKEN_DOMAIN = "app_gmail_oauth_token"


os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")


def _materialize_oauth_client_config(configured: str, target_filename: str) -> str:
    raw_value = str(configured or "").strip()
    if not raw_value:
        return ""

    candidate_path = Path(raw_value)
    if candidate_path.exists():
        return str(candidate_path)

    payload_text = raw_value
    parsed_payload: dict | None = None

    try:
        parsed_payload = json.loads(payload_text)
    except Exception:
        parsed_payload = None

    if parsed_payload is None:
        try:
            decoded = base64.b64decode(payload_text).decode("utf-8")
            parsed_payload = json.loads(decoded)
            payload_text = decoded
        except Exception:
            parsed_payload = None

    if not isinstance(parsed_payload, dict):
        return ""

    target_path = runtime_root() / target_filename
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(payload_text, encoding="utf-8")
    try:
        target_path.chmod(0o600)
    except Exception:
        pass
    return str(target_path)


def _oauth_client_credentials_path() -> str:
    configured = (settings.gmail_oauth_client_json or "").strip()
    if configured:
        materialized = _materialize_oauth_client_config(configured, "gmail-oauth-client.json")
        if materialized:
            return materialized
        return configured
    local_fallback = Path(__file__).resolve().parents[1] / "gmail-oauth-client.json"
    if local_fallback.exists():
        return str(local_fallback)
    return ""


def _oauth_token_path() -> Path:
    configured = (settings.gmail_oauth_token_json or "").strip()
    if configured:
        return Path(configured)
    return runtime_root() / "gmail-oauth-token.json"


def _supabase_gmail_token_enabled() -> bool:
    return supabase_store.is_enabled() and supabase_store.supports_domain(_GMAIL_OAUTH_TOKEN_DOMAIN)


def has_oauth_client_config() -> bool:
    client_path = _oauth_client_credentials_path()
    return bool(client_path and Path(client_path).exists())


def _save_user_credentials(creds: UserCredentials) -> None:
    if _supabase_gmail_token_enabled():
        supabase_store.replace_domain_rows(
            _GMAIL_OAUTH_TOKEN_DOMAIN,
            [{"token_json": creds.to_json(), "updated_at": int(time.time())}],
        )
        return
    token_path = _oauth_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    try:
        token_path.chmod(0o600)
    except Exception:
        pass


def _load_user_credentials_file() -> UserCredentials | None:
    if _supabase_gmail_token_enabled():
        try:
            rows = supabase_store.fetch_domain_rows(_GMAIL_OAUTH_TOKEN_DOMAIN)
        except Exception:
            rows = []
        token_json = str((rows[0] or {}).get("token_json") or "").strip() if rows else ""
        if not token_json:
            return None
        try:
            payload = json.loads(token_json)
            return UserCredentials.from_authorized_user_info(payload)
        except Exception:
            return None
    token_path = _oauth_token_path()
    if not token_path.exists():
        return None
    try:
        creds = UserCredentials.from_authorized_user_file(str(token_path))
    except Exception:
        return None
    return creds


def _load_user_credentials_with_status(required_scopes: list[str] | tuple[str, ...] | None = None) -> tuple[UserCredentials | None, str]:
    creds = _load_user_credentials_file()
    if not creds:
        return None, "missing_token"
    if required_scopes and not _has_required_scopes(creds, required_scopes):
        return None, "missing_scope"
    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            _save_user_credentials(creds)
        except Exception:
            return None, "revoked_or_expired"
    if creds.valid:
        if required_scopes and not _has_required_scopes(creds, required_scopes):
            return None, "missing_scope"
        return creds, "ok"
    return None, "invalid_token"


def _credential_scopes(creds: UserCredentials | None) -> set[str]:
    if not creds:
        return set()
    return {str(scope).strip() for scope in (creds.scopes or []) if str(scope).strip()}


def _has_required_scopes(creds: UserCredentials | None, required_scopes: list[str] | tuple[str, ...]) -> bool:
    if not creds:
        return False
    granted = _credential_scopes(creds)
    return all(scope in granted for scope in required_scopes)


def load_user_credentials(required_scopes: list[str] | tuple[str, ...] | None = None) -> UserCredentials | None:
    creds, _ = _load_user_credentials_with_status(required_scopes)
    return creds


def gmail_oauth_send_status() -> str:
    _, status = _load_user_credentials_with_status([GMAIL_SEND_SCOPE])
    return status


def gmail_connection_status() -> dict:
    raw_creds = _load_user_credentials_file()
    user_creds = load_user_credentials()
    granted_scopes = sorted(_credential_scopes(raw_creds))
    return {
        "mode": "oauth" if user_creds else "unconfigured",
        "oauth_ready": bool(user_creds),
        "oauth_client_configured": has_oauth_client_config(),
        "can_send": bool(load_user_credentials([GMAIL_SEND_SCOPE])),
        "can_read": bool(load_user_credentials([GMAIL_READ_SCOPE])),
        "granted_scopes": granted_scopes,
        "token_present": bool(raw_creds),
        "send_status": gmail_oauth_send_status(),
        "redirect_uri": settings.gmail_oauth_redirect_uri,
        "token_path": f"supabase:{_GMAIL_OAUTH_TOKEN_DOMAIN}" if _supabase_gmail_token_enabled() else str(_oauth_token_path()),
        "client_path": _oauth_client_credentials_path(),
    }


def build_oauth_authorization_url() -> tuple[str, str]:
    client_path = _oauth_client_credentials_path()
    if not client_path:
        raise FileNotFoundError(
            "חסר קובץ OAuth ל-Gmail. שמור את קובץ ה-client בתור gmail-oauth-client.json בשורש הפרויקט."
        )
    flow = Flow.from_client_secrets_file(
        client_path,
        scopes=GMAIL_SCOPES,
        redirect_uri=settings.gmail_oauth_redirect_uri,
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url, state


def exchange_oauth_code(authorization_response_url: str, state: str | None = None) -> dict:
    client_path = _oauth_client_credentials_path()
    if not client_path:
        raise FileNotFoundError(
            "חסר קובץ OAuth ל-Gmail. שמור את קובץ ה-client בתור gmail-oauth-client.json בשורש הפרויקט."
        )
    flow = Flow.from_client_secrets_file(
        client_path,
        scopes=GMAIL_SCOPES,
        redirect_uri=settings.gmail_oauth_redirect_uri,
        state=state,
    )
    flow.fetch_token(authorization_response=authorization_response_url)
    _save_user_credentials(flow.credentials)
    return gmail_connection_status()


def send_mail_via_gmail_api(
    recipients: list[str],
    subject: str,
    body: str,
    html_body: str,
    attachments: list[str],
    sender_address: str,
    sender_name: str,
    inline_gif_path: str | Path | None = None,
    bcc_recipients: list[str] | None = None,
) -> None:
    creds = load_user_credentials([GMAIL_SEND_SCOPE])
    if not creds:
        raise RuntimeError("Gmail OAuth עדיין לא מחובר לחשבון השולח.")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_name, sender_address))
    visible_recipients = [item for item in (recipients or []) if str(item or "").strip()]
    hidden_recipients = [item for item in (bcc_recipients or []) if str(item or "").strip()]
    msg["To"] = ", ".join(visible_recipients) if visible_recipients else "undisclosed-recipients:;"
    if hidden_recipients:
        msg["Bcc"] = ", ".join(hidden_recipients)
    msg.set_content(body)
    msg.add_alternative(html_body, subtype="html")

    html_part = msg.get_payload()[-1]
    if inline_gif_path:
        gif_path = Path(inline_gif_path)
        if gif_path.exists() and gif_path.is_file():
            html_part.add_related(
                gif_path.read_bytes(),
                maintype="image",
                subtype="gif",
                cid="<ben_yacov_logo>",
                filename=gif_path.name,
                disposition="inline",
            )

    for attachment_path in attachments:
        attachment_file = Path(attachment_path)
        if not attachment_file.exists() or not attachment_file.is_file():
            continue
        mime_type, _ = mimetypes.guess_type(str(attachment_file))
        maintype, subtype = (mime_type.split("/", 1) if mime_type else ("application", "octet-stream"))
        msg.add_attachment(
            attachment_file.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=attachment_file.name,
        )

    raw_message = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
    service = build("gmail", "v1", credentials=creds)
    service.users().messages().send(userId="me", body={"raw": raw_message}).execute()


def _gmail_service():
    creds = load_user_credentials([GMAIL_READ_SCOPE])
    if not creds:
        raise RuntimeError("Gmail OAuth לא מחובר עם הרשאת קריאה לתיבת השולח.")
    return build("gmail", "v1", credentials=creds)


def _decode_gmail_body(data: str) -> str:
    raw = str(data or "").strip()
    if not raw:
        return ""
    padded = raw + "=" * ((4 - len(raw) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _extract_plain_text_from_payload(payload: dict | None) -> str:
    if not isinstance(payload, dict):
        return ""
    mime_type = str(payload.get("mimeType") or "").lower()
    body = payload.get("body") or {}
    if mime_type == "text/plain":
        return _decode_gmail_body(body.get("data") or "")
    for part in payload.get("parts") or []:
        text = _extract_plain_text_from_payload(part)
        if text.strip():
            return text
    if mime_type == "text/html":
        html_text = _decode_gmail_body(body.get("data") or "")
        if html_text:
            html_text = re.sub(r"<br\s*/?>", "\n", html_text, flags=re.IGNORECASE)
            html_text = re.sub(r"</p\s*>", "\n", html_text, flags=re.IGNORECASE)
            html_text = re.sub(r"<[^>]+>", " ", html_text)
            html_text = re.sub(r"\s+", " ", html_text)
            return html_text.strip()
    return ""


def _extract_contact_name_from_body(text: str) -> str:
    raw = str(text or "").strip()
    if not raw:
        return ""
    match = re.search(r"שלום\s+([^\n,<>]{1,80})", raw)
    if not match:
        return ""
    contact = re.sub(r"\s+", " ", match.group(1)).strip(" -,:")[:80]
    for suffix in (
        " ושבוע טוב",
        " ובוקר טוב",
        " וערב טוב",
        " וצהריים טובים",
        " ויום טוב",
        " ויום נעים",
    ):
        if contact.endswith(suffix):
            contact = contact[: -len(suffix)].strip(" -,:")
            break
    return contact


def _parse_recipients(headers: list[dict]) -> list[str]:
    values = []
    for header in headers or []:
        if str(header.get("name") or "").lower() not in {"to", "cc"}:
            continue
        values.append(str(header.get("value") or ""))
    recipients = []
    for _, email in getaddresses(values):
        cleaned = str(email or "").strip()
        if cleaned and cleaned not in recipients:
            recipients.append(cleaned)
    return recipients


def _header_value(headers: list[dict], target: str) -> str:
    target = str(target or "").lower()
    for header in headers or []:
        if str(header.get("name") or "").lower() == target:
            return str(header.get("value") or "").strip()
    return ""


def _formatted_sent_at(headers: list[dict]) -> str:
    sent_raw = _header_value(headers, "date")
    if not sent_raw:
        return ""
    try:
        return format_datetime(parsedate_to_datetime(sent_raw))
    except Exception:
        return sent_raw


def _message_match_score(quote_number: str, subject: str, body_text: str) -> int:
    quote_number = str(quote_number or "").strip()
    if not quote_number:
        return 0
    subject_text = str(subject or "")
    body = str(body_text or "")
    if quote_number in subject_text:
        return 3
    if quote_number in body:
        return 2
    normalized_body = re.sub(r"\D+", "", body)
    normalized_quote = re.sub(r"\D+", "", quote_number)
    if normalized_quote and normalized_quote in normalized_body:
        return 1
    return 0


def _extract_sent_candidate_from_message(message: dict, quote_number: str) -> dict:
    payload = message.get("payload") or {}
    headers = payload.get("headers") or []
    body_text = _extract_plain_text_from_payload(payload)
    subject = _header_value(headers, "subject")
    sent_at = _formatted_sent_at(headers)
    return {
        "emails": _parse_recipients(headers),
        "subject": subject,
        "sent_at": sent_at,
        "contact_name": _extract_contact_name_from_body(body_text),
        "_match_score": _message_match_score(quote_number, subject, body_text),
    }


def find_latest_sent_mail_by_quote_number(quote_number: str) -> dict:
    quote_number = str(quote_number or "").strip()
    if not quote_number:
        return {}
    try:
        service = _gmail_service()
        thread_ids: list[str] = []
        seen_threads: set[str] = set()
        for query in (f'in:sent "{quote_number}"', f'"{quote_number}"'):
            listed = service.users().messages().list(userId="me", q=query, maxResults=25).execute()
            for message in listed.get("messages") or []:
                thread_id = str(message.get("threadId") or "").strip()
                if thread_id and thread_id not in seen_threads:
                    seen_threads.add(thread_id)
                    thread_ids.append(thread_id)

        if not thread_ids:
            return {}

        sent_candidates: list[tuple[int, str, dict]] = []
        for thread_id in thread_ids:
            thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
            for message in thread.get("messages") or []:
                label_ids = {str(label).upper() for label in (message.get("labelIds") or [])}
                if "SENT" not in label_ids:
                    continue
                candidate = _extract_sent_candidate_from_message(message, quote_number)
                match_score = int(candidate.pop("_match_score", 0) or 0)
                if not candidate.get("emails") and not candidate.get("subject") and not candidate.get("contact_name"):
                    continue
                sent_candidates.append((max(match_score, 1), str(candidate.get("sent_at") or ""), candidate))

        if not sent_candidates:
            return {}

        sent_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        _, _, best_candidate = sent_candidates[0]
        return best_candidate
    except Exception:
        return {}
