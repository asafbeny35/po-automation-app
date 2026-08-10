from unittest.mock import MagicMock, patch

from services import ocr_service


def test_extract_openai_output_text_supports_responses_api_messages():
    payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "הזמנת רכש מס': 8293"},
                    {"type": "output_text", "text": "סה\"כ לתשלום: 12,991.80"},
                ],
            }
        ]
    }

    assert ocr_service._extract_openai_output_text(payload) == (
        "הזמנת רכש מס': 8293\nסה\"כ לתשלום: 12,991.80"
    )


def test_openai_ocr_sends_image_and_returns_text(monkeypatch):
    monkeypatch.setattr(ocr_service.settings, "openai_api_key", "test-key")
    monkeypatch.setattr(ocr_service.settings, "openai_model", "gpt-5-mini")

    response = MagicMock()
    response.json.return_value = {"output_text": "הייקון\n8293"}
    client = MagicMock()
    client.post.return_value = response
    client_context = MagicMock()
    client_context.__enter__.return_value = client

    with patch("services.ocr_service.httpx.Client", return_value=client_context):
        result = ocr_service._ocr_image_bytes_via_openai(b"png-bytes")

    assert result == "הייקון\n8293"
    response.raise_for_status.assert_called_once_with()
    request = client.post.call_args
    assert request.args[0] == "https://api.openai.com/v1/responses"
    assert request.kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert request.kwargs["json"]["model"] == "gpt-5-mini"
    image_part = request.kwargs["json"]["input"][0]["content"][1]
    assert image_part["type"] == "input_image"
    assert image_part["image_url"].startswith("data:image/png;base64,")


def test_openai_ocr_is_skipped_without_api_key(monkeypatch):
    monkeypatch.setattr(ocr_service.settings, "openai_api_key", "")

    with patch("services.ocr_service.httpx.Client") as client_class:
        result = ocr_service._ocr_image_bytes_via_openai(b"png-bytes")

    assert result == ""
    client_class.assert_not_called()
