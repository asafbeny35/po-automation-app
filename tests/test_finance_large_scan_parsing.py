"""סריקות גדולות וחשבון הארנונה של עיריית חיפה.

סריקת WhatsApp של חשבון ארנונה (1611x3045 נק') רונדרה בקנה מידה קבוע ל-PNG
של 13MB ב-base64 — מעל מגבלת ה-5MB לתמונה של Anthropic. הקריאה נדחתה,
ה-except בלע את השגיאה, והפרסר נפל בשקט לניחוש רגקסים על OCR משובש.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

import app
from services.ocr_service import _DRIVE_OCR_MAX_UPLOAD_BYTES, _shrink_image_bytes_for_upload

_MAX_B64 = app._VISION_IMAGE_MAX_B64_BYTES


def _page(width: float, height: float):
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    # מלבנים אפורים מדמים סריקה: PNG של עמוד ריק נדחס לכלום ולא בודק כלום
    for index in range(60):
        rect = fitz.Rect(0, index * (height / 60), width, (index + 0.5) * (height / 60))
        page.draw_rect(rect, color=(0.45, 0.5, 0.55), fill=(0.45, 0.5, 0.55))
    return doc, page


# ── תקרת המשקל של בלוק התמונה ────────────────────────────────────────────────

@pytest.mark.parametrize("width, height", [
    (1611, 3045),    # הסריקה מהשטח
    (2400, 4000),    # סריקה גדולה עוד יותר
    (595, 842),      # A4 רגיל
    (300, 1400),     # קבלה תרמית צרה וארוכה
])
def test_every_page_shape_fits_the_api_limit(width, height):
    doc, page = _page(width, height)
    block = app._vision_image_block_from_page(page)
    assert block is not None
    assert len(block["source"]["data"]) <= _MAX_B64
    doc.close()


def test_the_long_edge_is_capped_at_the_useful_resolution():
    """מעבר ל-1568px ה-API מקטין בעצמו — רינדור גדול יותר רק מנפח את הבקשה."""
    doc, page = _page(1611, 3045)
    block = app._vision_image_block_from_page(page)
    import base64
    pix = fitz.Pixmap(base64.b64decode(block["source"]["data"]))
    assert max(pix.width, pix.height) <= app._VISION_IMAGE_MAX_EDGE + 1
    doc.close()


def test_a_clip_is_rendered_zoomed_and_still_bounded():
    doc, page = _page(1611, 3045)
    crop = fitz.Rect(0, 3045 * 0.6, 1611, 3045)
    block = app._vision_image_block_from_page(page, clip=crop)
    assert block is not None and len(block["source"]["data"]) <= _MAX_B64
    doc.close()


def test_a_small_page_stays_png_for_sharpness():
    doc, page = _page(595, 842)
    block = app._vision_image_block_from_page(page)
    assert block["source"]["media_type"] == "image/png"
    doc.close()


def test_a_degenerate_page_is_refused_rather_than_guessed():
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    assert app._vision_image_block_from_page(page, clip=fitz.Rect(0, 0, 0, 0)) is None
    doc.close()


# ── העלאת OCR ל-Drive ────────────────────────────────────────────────────────

def test_an_oversized_scan_is_shrunk_below_the_upload_limit():
    # רעש אמיתי: עמוד גרפי נקי נדחס לכלום ולא מייצג סריקת צילום
    import os

    width, height = 1200, 2000
    png = fitz.Pixmap(fitz.csRGB, width, height, os.urandom(width * height * 3), False).tobytes("png")
    assert len(png) > _DRIVE_OCR_MAX_UPLOAD_BYTES      # אחרת הבדיקה לא בודקת כלום
    assert len(_shrink_image_bytes_for_upload(png, _DRIVE_OCR_MAX_UPLOAD_BYTES)) <= _DRIVE_OCR_MAX_UPLOAD_BYTES


def test_a_small_image_is_passed_through_untouched():
    payload = b"already-small"
    assert _shrink_image_bytes_for_upload(payload, _DRIVE_OCR_MAX_UPLOAD_BYTES) is payload


# ── חשבון הארנונה של עיריית חיפה ─────────────────────────────────────────────

ARNONA_OCR = """לכבוד
בן יעקב אסף
חשבון ארנונה והיטל שמירה לחודשים
gvia@haifa.muni.il
_ 37017779 3009582
| 09-10/2026 | 6200 |
8,683.74 [5 | אתמה 26 |775|
| 179.91 - היטלשמ 26 |775 | ספטמבר-אוקטובר |
₪ ( 8,863.65 (
הסכום לתשלום
|| 2725495418-6 | | 01/09/2026 = || הודעה זו חקבל תוקף של קבלה
"""


def test_the_haifa_arnona_bill_is_detected():
    assert app._finance_detect_haifa_arnona_invoice(ARNONA_OCR, "", "WhatsApp Scan.pdf") is True


def test_an_unrelated_document_is_not_detected():
    assert app._finance_detect_haifa_arnona_invoice("חשבונית מס פלציב עין הנציב", "", "x.pdf") is False


def test_the_arnona_bill_parses_to_the_printed_total(tmp_path):
    draft = app._finance_parse_haifa_arnona_invoice(ARNONA_OCR, "", "scan.pdf", tmp_path / "scan.pdf")
    assert draft["supplier_name"] == "עיריית חיפה"
    assert draft["total"] == "8863.65"           # 8,683.74 + 179.91, הסכום המוקף בסריקה
    assert draft["invoice_date"] == "01/09/2026"
    assert "09-10/2026" in draft["service_or_product"]


def test_a_municipal_bill_carries_no_deductible_vat(tmp_path):
    """חיוב עירוני — הרו"ח הבהיר שאין בו מע"מ תשומות."""
    draft = app._finance_parse_haifa_arnona_invoice(ARNONA_OCR, "", "scan.pdf", tmp_path / "scan.pdf")
    assert app._finance_parse_number(draft["vat"]) == 0
    assert draft["subtotal"] == draft["total"]
    assert app._finance_vat_disallowed_reason(
        draft["supplier_name"], draft["service_or_product"], draft["currency_code"]
    ) == "municipal"


def test_the_imputation_does_not_re_add_vat_to_the_arnona_row(tmp_path):
    """המנגנון שהחזיר מע"מ אחרי כל איפוס חייב להישאר חסום גם כאן."""
    draft = app._finance_parse_haifa_arnona_invoice(ARNONA_OCR, "", "scan.pdf", tmp_path / "scan.pdf")
    assert app._finance_parse_number(app._finance_impute_vat_from_total_if_needed(draft)["vat"]) == 0


def test_the_total_is_found_even_without_the_currency_marker(tmp_path):
    """בלי ה-₪ נשענים על כך שהסה"כ הוא צירוף שתי שורות החיוב."""
    text = ARNONA_OCR.replace("₪ ( 8,863.65 (", "8,863.65")
    draft = app._finance_parse_haifa_arnona_invoice(text, "", "scan.pdf", tmp_path / "scan.pdf")
    assert draft["total"] == "8863.65"
