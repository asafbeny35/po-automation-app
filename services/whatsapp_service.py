from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from typing import Any

import httpx

from .config import settings
from .whatsapp_web import send_files_via_whatsapp as send_files_via_whatsapp_web


class WhatsAppDeliveryError(RuntimeError):
    pass


def _normalize_phone_digits(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("0"):
        digits = f"972{digits[1:]}"
    return digits


def _normalize_twilio_phone(phone: str) -> str:
    digits = _normalize_phone_digits(phone)
    return f"whatsapp:+{digits}" if digits else ""


def _meta_is_configured() -> bool:
    return bool(
        str(settings.whatsapp_meta_access_token or "").strip()
        and str(settings.whatsapp_meta_phone_number_id or "").strip()
    )


def _twilio_is_configured() -> bool:
    return bool(
        str(settings.whatsapp_twilio_account_sid or "").strip()
        and str(settings.whatsapp_twilio_auth_token or "").strip()
        and str(settings.whatsapp_twilio_from or "").strip()
    )


def _railway_is_configured() -> bool:
    return bool(str(settings.whatsapp_railway_url or "").strip())


def resolve_whatsapp_provider() -> str:
    raw_provider = str(settings.whatsapp_provider or "").strip().lower()
    if raw_provider in {"meta", "meta_cloud", "meta-cloud", "cloud"}:
        return "meta_cloud"
    if raw_provider in {"twilio"}:
        return "twilio"
    if raw_provider in {"railway"}:
        return "railway"
    if raw_provider in {"web", "legacy_web", "whatsapp_web"}:
        return "web"
    if raw_provider in {"auto"}:
        if _railway_is_configured():
            return "railway"
        if _meta_is_configured():
            return "meta_cloud"
        if _twilio_is_configured():
            return "twilio"
        return "web"
    return "web"


def _guess_mime_type(file_path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(file_path))
    return mime_type or "application/octet-stream"


async def _send_text_via_meta(
    client: httpx.AsyncClient,
    *,
    endpoint: str,
    phone: str,
    message: str,
) -> dict[str, Any]:
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "text",
        "text": {"body": message},
    }
    response = await client.post(endpoint, json=payload)
    response.raise_for_status()
    return response.json()


async def _upload_media_via_meta(
    client: httpx.AsyncClient,
    *,
    media_endpoint: str,
    file_path: Path,
) -> str:
    mime_type = _guess_mime_type(file_path)
    with file_path.open("rb") as file_handle:
        response = await client.post(
            media_endpoint,
            data={
                "messaging_product": "whatsapp",
                "type": mime_type,
            },
            files={
                "file": (file_path.name, file_handle, mime_type),
            },
        )
    response.raise_for_status()
    payload = response.json()
    media_id = str(payload.get("id") or "").strip()
    if not media_id:
        raise WhatsAppDeliveryError(f"Meta media upload did not return media id for {file_path.name}.")
    return media_id


async def _send_file_via_meta(
    client: httpx.AsyncClient,
    *,
    endpoint: str,
    phone: str,
    file_path: Path,
) -> dict[str, Any]:
    media_endpoint = endpoint.rsplit("/", 1)[0] + "/media"
    media_id = await _upload_media_via_meta(client, media_endpoint=media_endpoint, file_path=file_path)
    mime_type = _guess_mime_type(file_path)
    if mime_type.startswith("image/"):
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "image",
            "image": {"id": media_id},
        }
    else:
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "document",
            "document": {
                "id": media_id,
                "filename": file_path.name,
            },
        }
    response = await client.post(endpoint, json=payload)
    response.raise_for_status()
    return {
        "media_id": media_id,
        "message": response.json(),
        "mime_type": mime_type,
        "file_name": file_path.name,
    }


async def _send_via_meta(phone: str, message: str, file_paths: list[str]) -> dict[str, Any]:
    normalized_phone = _normalize_phone_digits(phone)
    if not normalized_phone:
        raise WhatsAppDeliveryError("מספר הטלפון ל־WhatsApp חסר או לא תקין.")
    access_token = str(settings.whatsapp_meta_access_token or "").strip()
    phone_number_id = str(settings.whatsapp_meta_phone_number_id or "").strip()
    api_version = str(settings.whatsapp_meta_api_version or "v23.0").strip()
    if not access_token or not phone_number_id:
        raise WhatsAppDeliveryError("Meta WhatsApp Cloud API אינו מוגדר בשרת.")

    base_url = f"https://graph.facebook.com/{api_version}/{phone_number_id}"
    message_endpoint = f"{base_url}/messages"
    headers = {
        "Authorization": f"Bearer {access_token}",
    }
    deliveries: list[dict[str, Any]] = []

    async with httpx.AsyncClient(headers=headers, timeout=90.0) as client:
        if message.strip():
            deliveries.append(
                {
                    "kind": "text",
                    "result": await _send_text_via_meta(
                        client,
                        endpoint=message_endpoint,
                        phone=normalized_phone,
                        message=message.strip(),
                    ),
                }
            )

        for raw_path in file_paths:
            file_path = Path(raw_path)
            if not file_path.exists() or not file_path.is_file():
                raise WhatsAppDeliveryError(f"קובץ לא נמצא לשליחת WhatsApp: {file_path}")
            deliveries.append(
                {
                    "kind": "file",
                    "result": await _send_file_via_meta(
                        client,
                        endpoint=message_endpoint,
                        phone=normalized_phone,
                        file_path=file_path,
                    ),
                }
            )

    return {
        "status": "ok",
        "provider": "meta_cloud",
        "phone": normalized_phone,
        "deliveries": deliveries,
    }


async def _send_via_twilio(phone: str, message: str, file_paths: list[str]) -> dict[str, Any]:
    normalized_phone = _normalize_twilio_phone(phone)
    if not normalized_phone:
        raise WhatsAppDeliveryError("מספר הטלפון ל־WhatsApp חסר או לא תקין.")
    if file_paths:
        raise WhatsAppDeliveryError(
            "מסלול Twilio עדיין לא תומך אצלנו בשליחת קבצים ישירות מהשרת ללא URL ציבורי לקבצים."
        )

    account_sid = str(settings.whatsapp_twilio_account_sid or "").strip()
    auth_token = str(settings.whatsapp_twilio_auth_token or "").strip()
    from_number = str(settings.whatsapp_twilio_from or "").strip()
    if not account_sid or not auth_token or not from_number:
        raise WhatsAppDeliveryError("Twilio WhatsApp אינו מוגדר בשרת.")

    endpoint = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
    payload = {
        "To": normalized_phone,
        "From": from_number,
        "Body": message.strip(),
    }
    async with httpx.AsyncClient(auth=(account_sid, auth_token), timeout=60.0) as client:
        response = await client.post(endpoint, data=payload)
        response.raise_for_status()
        return {
            "status": "ok",
            "provider": "twilio",
            "phone": normalized_phone,
            "deliveries": [response.json()],
        }


async def _send_via_railway(phone: str, message: str, file_paths: list[str]) -> dict[str, Any]:
    import base64
    base_url = str(settings.whatsapp_railway_url or "").rstrip("/")
    secret = str(settings.whatsapp_railway_secret or "")
    files = []
    for fp in file_paths:
        path = Path(fp)
        files.append({
            "name": path.name,
            "content_b64": base64.b64encode(path.read_bytes()).decode(),
            "size_bytes": path.stat().st_size,
        })
    payload: dict[str, Any] = {"phone": phone, "message": message, "files": files}
    if secret:
        payload["secret"] = secret
    async with httpx.AsyncClient(timeout=300) as client:
        response = await client.post(f"{base_url}/send", json=payload)
        response.raise_for_status()
        return {"status": "ok", "provider": "railway", **response.json()}


async def send_files_via_whatsapp(phone: str, message: str, file_paths: list[str]) -> dict[str, Any]:
    provider = resolve_whatsapp_provider()
    if provider == "meta_cloud":
        return await _send_via_meta(phone=phone, message=message, file_paths=file_paths)
    if provider == "twilio":
        return await _send_via_twilio(phone=phone, message=message, file_paths=file_paths)
    if provider == "railway":
        return await _send_via_railway(phone=phone, message=message, file_paths=file_paths)
    await send_files_via_whatsapp_web(phone=phone, message=message, file_paths=file_paths)
    return {
        "status": "ok",
        "provider": "web",
        "phone": _normalize_phone_digits(phone),
        "deliveries": [{"kind": "web"}],
    }
