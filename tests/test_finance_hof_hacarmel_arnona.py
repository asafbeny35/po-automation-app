"""חשבון תקופתי ארנונה של מועצה אזורית חוף הכרמל (סריקה, 01.10.2026).

לאותה מועצה שני מסמכים שונים לגמרי: חשבון מים וביוב (שהפרסר הכיר) וחשבון
ארנונה — העוגנים של המים לא קיימים בארנונה והסכומים יצאו ריקים. מלכודות
ה-OCR: הסכום מופיע פעם "636.70" ופעם "636 70" (רווח במקום נקודה), ושורת
הסכום יושבת כמה שורות לפני התווית "הסכום לתשלום".
"""
from __future__ import annotations

from pathlib import Path

import pytest

import app


# תמצית נאמנה של פלט ה-OCR האמיתי (OpenAI fallback) מהסריקה
OCR_TEXT = """לכבוד
בן יעקב דוד ומלכה הגורן 34
תל - אבים עתלית 3030000
המועצה האזורית חוף הכרמל מחלקת גבייה וארנונה
מס' רשות 32160 קוד מוטב 61-52844
פרטי המשלם
בן יעקב דוד ומלכה הגורן 34 עתלית
חשבון תקופתי ארנונה
ויתרת פיגורים
תקופת החשבון
09-10/26
תקופת ארנונה
לתשלום באינטרנט: www.hof-hacarmel.co.il
הסכום
1,351,40 -1,081 20
1010
סוג שרות תאור השירות ארנונה
חיוב תקופתי 1351.4 09/26קוד הנחה 1081.2 243
נכות אי-כושר 80%
636.70
טלת
שקל חדש
הסכום לתשלום
₪
15/09/26
לתשלום עד
30312121
מספר מסלקה
חשבון תקופתי ארנונה
636 70 (3)
קלח
הסכום לתשלום
₪
תקופת ארנונה
30312121
מספר מסלקה
לתשלום עד
15/09/26"""


@pytest.fixture(scope="module")
def parsed(tmp_path_factory):
    file_path = tmp_path_factory.mktemp("arnona") / "doc00428320261001103652.pdf"
    file_path.write_bytes(b"%PDF-1.4 stub")
    return app._finance_parse_hof_hacarmel_invoice(OCR_TEXT, OCR_TEXT, file_path.name, file_path)


# ── זיהוי ────────────────────────────────────────────────────────────────────

def test_the_arnona_scan_is_detected():
    assert app._finance_detect_hof_hacarmel_invoice(OCR_TEXT, OCR_TEXT, "doc.pdf") is True


def test_arnona_with_hof_hacarmel_alone_is_enough():
    assert app._finance_detect_hof_hacarmel_invoice("ארנונה חוף הכרמל", "", "doc.pdf") is True


# ── חילוץ ────────────────────────────────────────────────────────────────────

def test_the_supplier_is_the_council(parsed):
    assert parsed["supplier_name"] == "מועצה אזורית חוף הכרמל"


def test_the_total_is_pulled_from_the_label_window(parsed):
    """הסכום יושב לפני "הסכום לתשלום" — לא אחריה."""
    assert parsed["total"] == "636.70"
    assert parsed["subtotal"] == "636.70"


def test_municipal_charge_has_no_input_vat(parsed):
    assert parsed["vat"] == "0.00"


def test_the_invoice_date_is_the_pay_by_date(parsed):
    assert parsed["invoice_date"] == "15/09/2026"


def test_the_period_is_in_the_service_label(parsed):
    assert parsed["service_or_product"] == "חשבון תקופתי ארנונה 09-10/26"


def test_the_clearing_number_is_the_reference(parsed):
    assert parsed["reference_number"] == "30312121"


def test_the_space_for_dot_ocr_variant_still_yields_the_total():
    """כשההופעה הנקייה חסרה, "636 70" לבדה מספיקה."""
    garbled = OCR_TEXT.replace("636.70", "ללא סכום")
    file_path = Path("/tmp/arnona-garbled.pdf")
    result = app._finance_parse_hof_hacarmel_invoice(garbled, garbled, "doc.pdf", file_path)
    assert result["total"] == "636.70"


# ── המסמך של המים לא נחטף ────────────────────────────────────────────────────

def test_the_water_bill_still_uses_the_water_branch():
    water_text = "מועצה אזורית חוף הכרמל\nחשבון מים וביוב\n6333004 28/05/2026 412.30\n"
    result = app._finance_parse_hof_hacarmel_invoice(water_text, water_text, "water.pdf", Path("/tmp/water.pdf"))
    assert "מים וביוב" in result["service_or_product"]
    assert result["total"] == "412.30"
