from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from .config import settings
from . import supabase_store
from .google_service_account import build_service_account_credentials, resolve_service_account_source
from .runtime_paths import runtime_root


DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
_GOOGLE_DRIVE_OAUTH_TOKEN_DOMAIN = "app_google_drive_oauth_token"


class GoogleDriveSharedDriveRequiredError(RuntimeError):
    pass


# Local desktop app flow runs on http://localhost, so OAuth needs explicit opt-in
# for insecure transport in development.
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")


def _service_account_credentials_path() -> str:
    source_kind, payload = resolve_service_account_source()
    if source_kind != "file":
        raise FileNotFoundError("GOOGLE_SERVICE_ACCOUNT_JSON הוגדר כ-JSON ישיר, אין נתיב קובץ מקומי להצגה.")
    return str(payload)


def _oauth_client_credentials_path() -> str:
    configured = (settings.google_drive_oauth_client_json or "").strip()
    if configured:
        return configured
    local_fallback = Path(__file__).resolve().parents[1] / "google-drive-oauth-client.json"
    if local_fallback.exists():
        return str(local_fallback)
    return ""


def _oauth_token_path() -> Path:
    configured = (settings.google_drive_oauth_token_json or "").strip()
    if configured:
        return Path(configured)
    return runtime_root() / "google-drive-oauth-token.json"


def _supabase_drive_token_enabled() -> bool:
    return supabase_store.is_enabled() and supabase_store.supports_domain(_GOOGLE_DRIVE_OAUTH_TOKEN_DOMAIN)


def has_oauth_client_config() -> bool:
    client_path = _oauth_client_credentials_path()
    return bool(client_path and Path(client_path).exists())


def _save_user_credentials(creds: UserCredentials) -> None:
    if _supabase_drive_token_enabled():
        supabase_store.replace_domain_rows(
            _GOOGLE_DRIVE_OAUTH_TOKEN_DOMAIN,
            [{"token_json": creds.to_json()}],
        )
        return
    token_path = _oauth_token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    try:
        token_path.chmod(0o600)
    except Exception:
        pass


def load_user_credentials() -> UserCredentials | None:
    if _supabase_drive_token_enabled():
        try:
            rows = supabase_store.fetch_domain_rows(_GOOGLE_DRIVE_OAUTH_TOKEN_DOMAIN)
        except Exception:
            rows = []
        token_json = str((rows[0] or {}).get("token_json") or "").strip() if rows else ""
        if not token_json:
            return None
        try:
            payload = json.loads(token_json)
            creds = UserCredentials.from_authorized_user_info(payload, DRIVE_SCOPES)
        except Exception:
            return None
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            _save_user_credentials(creds)
        return creds if creds.valid else None
    token_path = _oauth_token_path()
    if not token_path.exists():
        return None
    try:
        creds = UserCredentials.from_authorized_user_file(str(token_path), DRIVE_SCOPES)
    except Exception:
        return None
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_user_credentials(creds)
    if creds.valid:
        return creds
    return None


def google_drive_connection_status() -> dict:
    user_creds = load_user_credentials()
    return {
        "mode": "oauth" if user_creds else "service_account",
        "oauth_ready": bool(user_creds),
        "oauth_client_configured": has_oauth_client_config(),
        "redirect_uri": settings.google_drive_oauth_redirect_uri,
        "token_path": f"supabase:{_GOOGLE_DRIVE_OAUTH_TOKEN_DOMAIN}" if _supabase_drive_token_enabled() else str(_oauth_token_path()),
        "client_path": _oauth_client_credentials_path(),
    }


def build_oauth_authorization_url() -> tuple[str, str]:
    client_path = _oauth_client_credentials_path()
    if not client_path:
        raise FileNotFoundError(
            "חסר קובץ OAuth ל-Google Drive. שמור את קובץ ה-client בתור google-drive-oauth-client.json בשורש הפרויקט."
        )
    flow = Flow.from_client_secrets_file(
        client_path,
        scopes=DRIVE_SCOPES,
        redirect_uri=settings.google_drive_oauth_redirect_uri,
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
            "חסר קובץ OAuth ל-Google Drive. שמור את קובץ ה-client בתור google-drive-oauth-client.json בשורש הפרויקט."
        )
    flow = Flow.from_client_secrets_file(
        client_path,
        scopes=DRIVE_SCOPES,
        redirect_uri=settings.google_drive_oauth_redirect_uri,
        state=state,
    )
    flow.fetch_token(authorization_response=authorization_response_url)
    creds = flow.credentials
    _save_user_credentials(creds)
    return google_drive_connection_status()


def _service():
    user_creds = load_user_credentials()
    if user_creds:
        return build("drive", "v3", credentials=user_creds)
    creds = build_service_account_credentials(DRIVE_SCOPES)
    return build("drive", "v3", credentials=creds)


def service_account_email() -> str:
    try:
        creds = build_service_account_credentials(DRIVE_SCOPES)
        return str(getattr(creds, "service_account_email", "") or "").strip()
    except Exception:
        return ""


def drive_item_metadata(file_id: str) -> dict:
    service = _service()
    record = service.files().get(
        fileId=file_id,
        fields="id,name,mimeType,driveId,parents,webViewLink,webContentLink,owners(displayName,emailAddress),capabilities(canAddChildren)",
        supportsAllDrives=True,
    ).execute()
    owners = []
    for owner in record.get("owners") or []:
        owners.append(
            {
                "display_name": str(owner.get("displayName") or "").strip(),
                "email_address": str(owner.get("emailAddress") or "").strip(),
            }
        )
    return {
        "id": str(record.get("id") or "").strip(),
        "name": str(record.get("name") or "").strip(),
        "mime_type": str(record.get("mimeType") or "").strip(),
        "drive_id": str(record.get("driveId") or "").strip(),
        "parents": [str(item or "").strip() for item in (record.get("parents") or []) if str(item or "").strip()],
        "web_view_link": str(record.get("webViewLink") or "").strip(),
        "web_content_link": str(record.get("webContentLink") or "").strip(),
        "owners": owners,
        "can_add_children": bool((record.get("capabilities") or {}).get("canAddChildren")),
    }


def validate_shared_drive_folder(folder_id: str, label: str = "Drive root") -> dict:
    target_id = str(folder_id or "").strip()
    if not target_id:
        raise GoogleDriveSharedDriveRequiredError(f"חסר מזהה תיקייה עבור {label}.")
    metadata = drive_item_metadata(target_id)
    if metadata.get("mime_type") != "application/vnd.google-apps.folder":
        raise GoogleDriveSharedDriveRequiredError(f"{label} חייב להיות תיקייה ב-Google Drive.")
    if not metadata.get("drive_id"):
        folder_name = metadata.get("name") or target_id
        raise GoogleDriveSharedDriveRequiredError(
            f"{label} ({folder_name}) נמצא ב-My Drive ולא ב-Shared Drive. "
            "Service account לא יכול להחזיק קבצים שם. יש לבחור תיקיית root מתוך Shared Drive."
        )
    return metadata


def managed_storage_root_folder_id() -> str:
    root_id = str(settings.google_drive_orders_root_folder_id or "").strip()
    if not root_id:
        raise GoogleDriveSharedDriveRequiredError("חסר GOOGLE_DRIVE_ORDERS_ROOT_FOLDER_ID עבור אחסון Drive מנוהל.")
    validate_shared_drive_folder(root_id, "GOOGLE_DRIVE_ORDERS_ROOT_FOLDER_ID")
    return root_id


def google_drive_health_summary() -> dict:
    status = google_drive_connection_status()
    root_id = str(settings.google_drive_orders_root_folder_id or "").strip()
    root_metadata: dict = {}
    root_error = ""
    if root_id:
        try:
            root_metadata = validate_shared_drive_folder(root_id, "GOOGLE_DRIVE_ORDERS_ROOT_FOLDER_ID")
        except Exception as exc:
            root_error = str(exc)
            try:
                root_metadata = drive_item_metadata(root_id)
            except Exception:
                root_metadata = {}
    else:
        root_error = "חסר GOOGLE_DRIVE_ORDERS_ROOT_FOLDER_ID."
    return {
        **status,
        "service_account_email": service_account_email(),
        "managed_root_folder_id": root_id,
        "managed_root_folder_name": str(root_metadata.get("name") or "").strip(),
        "managed_root_drive_id": str(root_metadata.get("drive_id") or "").strip(),
        "managed_root_is_shared_drive": bool(root_metadata.get("drive_id")),
        "managed_root_can_add_children": bool(root_metadata.get("can_add_children")),
        "managed_root_owner_emails": [str(item.get("email_address") or "").strip() for item in (root_metadata.get("owners") or []) if str(item.get("email_address") or "").strip()],
        "root_error": root_error,
    }


def _find_child_folder(service, parent_id: str, title: str) -> str | None:
    safe_title = title.replace("'", "\\'")
    query = (
        f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' "
        f"and trashed = false and name = '{safe_title}'"
    )
    result = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id,name)",
        pageSize=20,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()
    files = result.get("files", [])
    return str(files[0]["id"]) if files else None


def _find_file_in_folder(service, parent_id: str, title: str) -> dict | None:
    safe_title = title.replace("'", "\\'")
    query = (
        f"'{parent_id}' in parents and mimeType != 'application/vnd.google-apps.folder' "
        f"and trashed = false and name = '{safe_title}'"
    )
    result = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id,name,webViewLink,webContentLink)",
        pageSize=20,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute()
    files = result.get("files", [])
    if not files:
        return None
    first = files[0]
    return {
        "id": str(first.get("id") or ""),
        "name": str(first.get("name") or ""),
        "web_view_link": str(first.get("webViewLink") or ""),
        "web_content_link": str(first.get("webContentLink") or ""),
    }


def ensure_child_folder(parent_id: str, title: str) -> str:
    service = _service()
    existing = _find_child_folder(service, parent_id, title)
    if existing:
        return existing
    payload = {
        "name": title,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    created = service.files().create(
        body=payload,
        fields="id,name",
        supportsAllDrives=True,
    ).execute()
    return str(created["id"])


def list_child_folders(parent_id: str) -> list[dict]:
    service = _service()
    query = (
        f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' "
        "and trashed = false"
    )
    result = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id,name,webViewLink)",
        pageSize=1000,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        orderBy="name_natural",
    ).execute()
    folders = []
    for item in result.get("files", []) or []:
        folders.append(
            {
                "id": str(item.get("id") or "").strip(),
                "name": str(item.get("name") or "").strip(),
                "web_view_link": str(item.get("webViewLink") or "").strip(),
            }
        )
    return folders


def list_folder_files(parent_id: str) -> list[dict]:
    service = _service()
    query = (
        f"'{parent_id}' in parents and mimeType != 'application/vnd.google-apps.folder' "
        "and trashed = false"
    )
    result = service.files().list(
        q=query,
        spaces="drive",
        fields="files(id,name,webViewLink,webContentLink,mimeType)",
        pageSize=1000,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
        orderBy="name_natural",
    ).execute()
    files: list[dict] = []
    for item in result.get("files", []) or []:
        files.append(
            {
                "id": str(item.get("id") or "").strip(),
                "name": str(item.get("name") or "").strip(),
                "mime_type": str(item.get("mimeType") or "").strip(),
                "web_view_link": str(item.get("webViewLink") or "").strip(),
                "web_content_link": str(item.get("webContentLink") or "").strip(),
            }
        )
    return files


def upload_file_to_folder(parent_id: str, file_path: str | Path, drive_name: str | None = None) -> dict:
    service = _service()
    file_path = Path(file_path)
    mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
    metadata = {
        "name": drive_name or file_path.name,
        "parents": [parent_id],
    }
    media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=False)
    created = service.files().create(
        body=metadata,
        media_body=media,
        fields="id,name,webViewLink,webContentLink",
        supportsAllDrives=True,
    ).execute()
    return {
        "id": str(created.get("id") or ""),
        "name": str(created.get("name") or ""),
        "web_view_link": str(created.get("webViewLink") or ""),
        "web_content_link": str(created.get("webContentLink") or ""),
    }


def ensure_file_in_folder(parent_id: str, file_path: str | Path, drive_name: str | None = None) -> dict:
    service = _service()
    file_path = Path(file_path)
    target_name = drive_name or file_path.name
    existing = _find_file_in_folder(service, parent_id, target_name)
    if existing:
        return existing
    return upload_file_to_folder(parent_id, file_path, drive_name=target_name)


def download_file(file_id: str, target_path: str | Path) -> Path:
    service = _service()
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    with target_path.open("wb") as handle:
        downloader = MediaIoBaseDownload(handle, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    return target_path


def delete_file(file_id: str) -> None:
    service = _service()
    service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
