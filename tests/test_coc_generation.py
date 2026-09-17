"""תעודות C.O.C — פלסן סאסא ופלסן רא"ם.

רא"ם מקבלת את אותה תעודה כמו סאסא, עם שני הבדלים (הנחיית אסף 16.09.2026):
הנמען, ושורת כמות שמסכמת את כל השורות בלי ציון מספר גלילים.
"""
from __future__ import annotations

import fitz
import pytest

import app
from services.coc_generator_pdf import coc_quantity_line, generate_coc_pdf


# ── פרופיל הלקוח ─────────────────────────────────────────────────────────────

@pytest.mark.parametrize("name, company, show_rolls", [
    ('פלסן סאסא בע"מ', "פלסן סאסא בע״מ", True),
    ("פלסן סאסא", "פלסן סאסא בע״מ", True),
    ("פלסן רא״מ", "פלסן רא״מ בע״מ", False),
    ('פלסן רא"מ-רכב אזרחי ממוגן בע"מ', "פלסן רא״מ בע״מ", False),
    ("פלסאן ראמ", "פלסן רא״מ בע״מ", False),   # האיות בספר הלקוחות המקומי
])
def test_both_plasan_customers_get_a_coc_profile(name, company, show_rolls):
    profile = app._coc_customer_profile(name)
    assert profile == {"company": company, "show_rolls": show_rolls}


@pytest.mark.parametrize("name", ["טובול ציוד וחומרי בניין", "אלמוג ב.ז בנייה והשקעות בעמ", ""])
def test_other_customers_get_none(name):
    assert app._coc_customer_profile(name) is None


# ── שער אישורי המסירה ────────────────────────────────────────────────────────

@pytest.mark.parametrize("company", ['פלסן סאסא בע"מ', "פלסן רא״מ", "פלסאן ראמ"])
def test_both_plasan_rows_require_coc_on_delivery_mail(company):
    assert app._is_plasan_delivery_confirmation_row({"company": company}) is True


def test_a_regular_customer_does_not_require_coc():
    assert app._is_plasan_delivery_confirmation_row({"company": "טובול"}) is False


# ── שורת הכמות ───────────────────────────────────────────────────────────────

def test_sasa_line_includes_rolls():
    assert coc_quantity_line("60", 30, True) == "כמות: 60 מ״ר | אספקה ב 30 גלילים"


def test_raam_line_is_square_meters_only():
    assert coc_quantity_line("288", 3, False) == "כמות: 288 מ״ר"


# ── התעודה עצמה ──────────────────────────────────────────────────────────────

def _pdf_text(payload) -> str:
    import tempfile
    from pathlib import Path

    target = Path(tempfile.mkdtemp()) / "coc.pdf"
    generate_coc_pdf(payload, str(target))
    return fitz.open(target)[0].get_text()


def test_the_raam_certificate(tmp_path):
    text = _pdf_text({
        "po": "56590", "sku": "1000058",
        "desc": "ריפוד גג אפור מחורר כולל מעכב בעירה 1.5*64",
        "qty": 288.0, "date": "16/09/2026", "rolls": 3,
        "company": "פלסן רא״מ בע״מ", "show_rolls": False,
    })
    assert "לכבוד: פלסן רא״מ בע״מ" in text
    assert "סאסא" not in text
    assert "288" in text and "56590" in text and "1000058" in text
    assert "גלילים" not in text               # רא"ם: בלי שורת גלילים
    assert "ריפוד גג אפור" in text            # התיאור העברי קריא ולא הפוך


def test_the_sasa_certificate_is_unchanged_with_the_old_contract(tmp_path):
    """פיילוד ישן בלי company/show_rolls — חוזה סאסא נשמר כלשונו."""
    text = _pdf_text({
        "po": "123456-01", "sku": "QTP-1",
        "desc": "QuietPipe acoustic sheet 2x1m",
        "qty": 60.0, "date": "01/09/2026", "rolls": 30,
    })
    assert "לכבוד: פלסן סאסא בע״מ" in text
    assert "גלילים" in text
    assert "30" in text and "60" in text
    assert "QuietPipe acoustic sheet 2x1m" in text


def test_the_hebrew_description_is_not_reversed(tmp_path):
    """centered לא הפעיל bidi כי אצל סאסא התיאור באנגלית — התיאור של רא"ם יצא הפוך
    על הדף (fitz מחלץ חזרה בסדר לוגי, אז טקסט הפוך בחילוץ = הפוך גם בעין)."""
    text = _pdf_text({
        "po": "1", "sku": "1", "desc": "ריפוד גג אפור",
        "qty": 96.0, "date": "16/09/2026", "rolls": 1,
        "company": "פלסן רא״מ בע״מ", "show_rolls": False,
    })
    assert "ריפוד גג אפור" in text
    assert "דופיר" not in text
