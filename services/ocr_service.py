"""
Cloud OCR service — Google Cloud Vision API.
Falls back to pytesseract if Vision is not configured.
Used by ocr_pdf() and image OCR calls throughout the app.
"""
from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

from .google_service_account import build_service_account_credentials


logger = logging.getLogger(__name__)


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


def ocr_image_file(file_path: Path) -> str:
    """OCR a single image file. Uses Vision API if available, else pytesseract."""
    image_bytes = file_path.read_bytes()
    result = _ocr_image_bytes_via_vision(image_bytes)
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
    OCR a PDF using Google Cloud Vision API.
    Rasterizes pages with PyMuPDF (fitz, already a dependency) — no poppler needed.
    Falls back to pytesseract+pdf2image if Vision not available.
    """
    # Try PyMuPDF rasterization + Vision API
    try:
        import fitz  # PyMuPDF
        from PIL import Image

        doc = fitz.open(str(pdf_path))
        page_texts = []
        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            img_bytes = pixmap.tobytes("png")
            text = _ocr_image_bytes_via_vision(img_bytes)
            page_texts.append(text)
        doc.close()
        result = "\n".join(page_texts)
        if result.strip():
            logger.info(
                "OCR PDF completed with Vision: pages=%s text_length=%s",
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
