from __future__ import annotations

import pytest

from services import whatsapp_service


@pytest.mark.unit
def test_resolve_provider_prefers_meta_when_auto_and_meta_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_provider", "auto", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_meta_access_token", "token", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_meta_phone_number_id", "phone-id", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_twilio_account_sid", "", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_twilio_auth_token", "", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_twilio_from", "", raising=False)

    assert whatsapp_service.resolve_whatsapp_provider() == "meta_cloud"


@pytest.mark.unit
def test_resolve_provider_prefers_twilio_when_auto_and_only_twilio_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_provider", "auto", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_meta_access_token", "", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_meta_phone_number_id", "", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_twilio_account_sid", "sid", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_twilio_auth_token", "secret", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_twilio_from", "whatsapp:+14155238886", raising=False)

    assert whatsapp_service.resolve_whatsapp_provider() == "twilio"


@pytest.mark.unit
def test_resolve_provider_falls_back_to_web_when_auto_and_no_provider_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_provider", "auto", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_meta_access_token", "", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_meta_phone_number_id", "", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_twilio_account_sid", "", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_twilio_auth_token", "", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_twilio_from", "", raising=False)

    assert whatsapp_service.resolve_whatsapp_provider() == "web"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_send_files_via_whatsapp_uses_legacy_web_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    called: dict[str, object] = {}

    async def fake_web_sender(*, phone: str, message: str, file_paths: list[str]) -> None:
        called["phone"] = phone
        called["message"] = message
        called["file_paths"] = list(file_paths)

    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_provider", "web", raising=False)
    monkeypatch.setattr(whatsapp_service, "send_files_via_whatsapp_web", fake_web_sender)

    result = await whatsapp_service.send_files_via_whatsapp(
        phone="0547720142",
        message="בדיקה",
        file_paths=["/tmp/test.pdf"],
    )

    assert called == {
        "phone": "0547720142",
        "message": "בדיקה",
        "file_paths": ["/tmp/test.pdf"],
    }
    assert result["provider"] == "web"
    assert result["status"] == "ok"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_twilio_path_rejects_direct_file_uploads(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_provider", "twilio", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_twilio_account_sid", "sid", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_twilio_auth_token", "secret", raising=False)
    monkeypatch.setattr(whatsapp_service.settings, "whatsapp_twilio_from", "whatsapp:+14155238886", raising=False)

    with pytest.raises(whatsapp_service.WhatsAppDeliveryError) as exc:
        await whatsapp_service.send_files_via_whatsapp(
            phone="0547720142",
            message="בדיקה",
            file_paths=["/tmp/test.pdf"],
        )

    assert "Twilio" in str(exc.value)
