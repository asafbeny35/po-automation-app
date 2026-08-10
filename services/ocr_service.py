"""
Cloud OCR service — Google Cloud Vision API.
Falls back to OpenAI, Anthropic, and then pytesseract if Vision is unavailable.
Used by ocr_pdf() and image OCR calls throughout the app.
"""
from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

from .config import settings
from .google_service_account import build_service_account_credentials


logger = logging.getLogger(__name__)


OCR_PROMPT = (
    "Perform exact OCR on this purchase-order page. Return only the visible text, "
    "without commentary or Markdown fences. Preserve table rows and line breaks as "
    "faithfully as possible. Keep every Hebrew and English word, number, date, SKU, "
    "quantity, dimension, price, address, phone number, subtotal, VAT, and total "
    "exactly as shown."
)


def _vision_client():
    try:
        from google.cloud import vision
        creds = build_service_account_credentials(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return vision.ImageAnnotatorClient(credentials=creds)
    except Exception as exc:
        logger.warning(
            "OCR Vision client unavailable: %s: %s",
            type(exc).__name__,
            exc,
        )
        return None


def _ocr_image_bytes_via_vision(image_bytes: bytes) -> str:
    client = _vision_client()
    if client is None:
        return ""
    try:
        from google.cloud import vision
        image = vision.Image(content=image_bytes)
        response = client.document_text_detection(image=image)
        if response.error.message:
            logger.error("OCR Vision API error: %s", response.error.message)
            return ""
        text = response.full_text_annotation.text or ""
        logger.info("OCR Vision image completed: text_length=%s", len(text.strip()))
        return text
    except Exception as exc:
        logger.exception("OCR Vision image request failed: %s", exc)
        return ""


def _extract_openai_output_text(payload: dict) -> str:
    """Extract assistant text from a Responses API payload."""
    direct_text = payload.get("output_text")
    if isinstance(direct_text, str) and direct_text.strip():
        return direct_text.strip()

    text_parts: list[str] = []
    for output_item in payload.get("output") or []:
        if not isinstance(output_item, dict):
            continue
        for content_item in output_item.get("content") or []:
            if not isinstance(content_item, dict):
                continue
            text = content_item.get("text")
            if isinstance(text, str) and text.strip():
                text_parts.append(text.strip())
    return "\n".join(text_parts)


def _ocr_image_bytes_via_openai(image_bytes: bytes) -> str:
    """OCR an image through the OpenAI Responses API."""
    if not settings.openai_api_key:
        logger.warning("OCR OpenAI fallback unavailable: OPENAI_API_KEY is not configured")
        return ""

    image_url = "data:image/png;base64," + base64.b64encode(image_bytes).decode("ascii")
    request_payload = {
        "model": settings.openai_model or "gpt-5-mini",
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": OCR_PROMPT,
                    },
                    {
                        "type": "input_image",
                        "image_url": image_url,
                        "detail": "high",
                    },
                ],
            }
        ],
        "max_output_tokens": 8000,
    }
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
        response.raise_for_status()
        text = _extract_openai_output_text(response.json())
        logger.info("OCR OpenAI image completed: text_length=%s", len(text))
        return text
    except Exception as exc:
        logger.exception("OCR OpenAI image request failed: %s", exc)
        return ""


def _extract_anthropic_output_text(payload: dict) -> str:
    """Extract text blocks from an Anthropic Messages API payload."""
    text_parts = []
    for content_item in payload.get("content") or []:
        if not isinstance(content_item, dict) or content_item.get("type") != "text":
            continue
        text = content_item.get("text")
        if isinstance(text, str) and text.strip():
            text_parts.append(text.strip())
    return "\n".join(text_parts)


def _ocr_image_bytes_via_anthropic(image_bytes: bytes) -> str:
    """OCR an image through the Anthropic Messages API."""
    if not settings.anthropic_api_key:
        logger.warning("OCR Anthropic fallback unavailable: ANTHROPIC_API_KEY is not configured")
        return ""

    request_payload = {
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 8000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        },
                    },
                    {"type": "text", "text": OCR_PROMPT},
                ],
            }
        ],
    }
    try:
        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": settings.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json=request_payload,
            )
        response.raise_for_status()
        text = _extract_anthropic_output_text(response.json())
        logger.info("OCR Anthropic image completed: text_length=%s", len(text))
        return text
    except Exception as exc:
        logger.exception("OCR Anthropic image request failed: %s", exc)
        return ""


def _ocr_image_bytes_via_cloud_fallbacks(image_bytes: bytes) -> str:
    """Try configured multimodal providers in order."""
    text = _ocr_image_bytes_via_openai(image_bytes)
    if text.strip():
        return text
    logger.warning("OCR OpenAI returned no text; using Anthropic fallback")
    return _ocr_image_bytes_via_anthropic(image_bytes)


def ocr_image_file(file_path: Path) -> str:
    """OCR a single image file with cloud fallbacks before local Tesseract."""
    image_bytes = file_path.read_bytes()
    result = _ocr_image_bytes_via_vision(image_bytes)
    if result:
        return result
    result = _ocr_image_bytes_via_cloud_fallbacks(image_bytes)
    if result:
        return result
    # fallback: pytesseract
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(file_path), lang="heb+eng")
        logger.info("OCR Tesseract image completed: text_length=%s", len(text.strip()))
        return text
    except Exception as exc:
        logger.warning("OCR image fallback unavailable: %s: %s", type(exc).__name__, exc)
        return ""


def ocr_pdf_via_vision(pdf_path: Path) -> str:
    """
    OCR a PDF using Google Cloud Vision API, with an OpenAI Vision fallback.
    Rasterizes pages with PyMuPDF (fitz, already a dependency) — no poppler needed.
    Falls back to pytesseract+pdf2image if Vision not available.
    """
    # Try PyMuPDF rasterization + Vision API
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(str(pdf_path))
        page_texts = []
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            img_bytes = pixmap.tobytes("png")
            text = _ocr_image_bytes_via_vision(img_bytes)
            if not text.strip():
                logger.warning(
                    "OCR Vision returned no text for page=%s; using OpenAI fallback",
                    page_num + 1,
                )
                text = _ocr_image_bytes_via_cloud_fallbacks(img_bytes)
            page_texts.append(text)
        doc.close()
        result = "\n".join(page_texts)
        if result.strip():
            logger.info(
                "OCR PDF completed with cloud OCR: pages=%s text_length=%s",
                len(page_texts),
                len(result.strip()),
            )
            return result
        logger.warning("OCR Vision returned no text: pages=%s", len(page_texts))
    except Exception as exc:
        logger.exception("OCR PDF Vision pipeline failed: %s", exc)

    # fallback: pytesseract + pdf2image (local only)
    try:
        import pytesseract
        from pdf2image import convert_from_path
        images = convert_from_path(str(pdf_path), dpi=300)
        text = "\n".join(pytesseract.image_to_string(img, lang="heb+eng") for img in images)
        logger.info(
            "OCR PDF completed with Tesseract: pages=%s text_length=%s",
            len(images),
            len(text.strip()),
        )
        return text
    except Exception as exc:
        logger.warning("OCR PDF fallback unavailable: %s: %s", type(exc).__name__, exc)
        return ""
