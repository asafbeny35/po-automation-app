"""
Cloud OCR service — Google Cloud Vision API.
Falls back to pytesseract if Vision is not configured.
Used by ocr_pdf() and image OCR calls throughout the app.
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

from .google_service_account import build_service_account_credentials


def _vision_client():
    try:
        from google.cloud import vision
        creds = build_service_account_credentials(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        return vision.ImageAnnotatorClient(credentials=creds)
    except Exception:
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
            return ""
        return response.full_text_annotation.text or ""
    except Exception:
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
        return pytesseract.image_to_string(Image.open(file_path), lang="heb+eng")
    except Exception:
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
            return result
    except Exception:
        pass

    # fallback: pytesseract + pdf2image (local only)
    try:
        import pytesseract
        from pdf2image import convert_from_path
        images = convert_from_path(str(pdf_path), dpi=300)
        return "\n".join(pytesseract.image_to_string(img, lang="heb+eng") for img in images)
    except Exception:
        return ""
