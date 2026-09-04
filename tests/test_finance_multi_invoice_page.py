"""כמה חשבוניות על עמוד סרוק אחד.

סורק שמניחים עליו שתי קבלות זו לצד זו מייצר עמוד אחד עם שני מסמכים. הפיצול
לפי עמודים לא יכול להפריד ביניהם, וכל מקרה כזה טופל עד היום ברשימת SHA1
מקודדת ידנית. הבדיקות כאן מכסות את כל מה שדטרמיניסטי: הסינון הזול שמחליט
אם בכלל לשלוח לראייה, המרת התיבה לנקודות PDF, החיתוך לקובץ נפרד, ובעיקר —
שאף שדה לא נודד מחשבונית אחת לשנייה.

קריאת הראייה עצמה מוחלפת בכפיל, כי מפתח Anthropic קיים רק בפרודקשן.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

import app

SCANS = Path(__file__).parent / "fixtures" / "pdfs"
TWO_ON_A_PAGE = SCANS / "scan_two_invoices.pdf"


# ── הסינון הזול שקובע אם בכלל שולחים לראייה ─────────────────────────────────

def test_two_business_ids_look_like_two_documents():
    assert app._finance_page_invoice_signal_count("ח.פ 516211950 ... ח.פ 512036104", "") > 1


def test_a_single_receipt_is_not_sent_to_vision():
    text = 'חשבונית מס/קבלה 6535\nח.פ 517302741\nסה"כ לתשלום 39.80'
    assert app._finance_page_invoice_signal_count(text, text) <= 1


def test_placeholder_ids_do_not_count_as_a_second_document():
    """‏999999999 הוא "לקוח כללי" בקבלות רבות, לא עסק נוסף."""
    text = "ח.פ 517302741 999999999 000000000"
    assert app._finance_page_invoice_signal_count(text, text) <= 1


# ── המרת התיבה לנקודות PDF ───────────────────────────────────────────────────

def test_a_normalised_box_becomes_pdf_points():
    rect = fitz.Rect(0, 0, 595, 842)
    got = app._finance_region_to_rect([0.0, 0.0, 0.5, 0.5], rect)
    # כולל שוליים קטנים כדי שקצה הקבלה לא ייחתך
    assert got[0] == 0 and got[1] == 0
    assert 297 < got[2] < 310
    assert 421 < got[3] < 435


def test_the_right_half_maps_to_the_right_half():
    got = app._finance_region_to_rect([0.5, 0.0, 1.0, 1.0], fitz.Rect(0, 0, 595, 842))
    assert got[0] < 300 and got[2] == 595


@pytest.mark.parametrize("bad", [None, [], [0, 0, 1], "0,0,1,1", [1, 0, 0, 1], [0, 1, 1, 0], ["a", 0, 1, 1]])
def test_a_broken_box_is_refused_rather_than_guessed(bad):
    assert app._finance_region_to_rect(bad, fitz.Rect(0, 0, 595, 842)) is None


# ── שדות לא נודדים בין חשבוניות ──────────────────────────────────────────────

def _entry(**over):
    base = {"supplier_name": "ספק", "invoice_date": "01/09/2026", "reference_number": "1",
            "subtotal": "10", "vat": "1.8", "total": "11.8", "currency": "ILS",
            "service_or_product": "משהו"}
    base.update(over)
    return base


def test_each_invoice_keeps_its_own_fields(tmp_path):
    src = tmp_path / "src.pdf"
    fitz.open().new_page(width=595, height=842).parent.save(src)
    page_invoices = [
        {"draft": app._finance_vision_invoice_to_draft(
            _entry(supplier_name="זכוכית 2000", reference_number="24265", total="200", subtotal="169.49", vat="30.51"),
            src, "src.pdf"), "rect": [300, 40, 595, 300]},
        {"draft": app._finance_vision_invoice_to_draft(
            _entry(supplier_name="פיצה גראז גבעתיים", reference_number="197705", total="58.00", subtotal="49.20", vat="8.90"),
            src, "src.pdf"), "rect": [0, 40, 300, 480]},
    ]
    drafts = app._finance_drafts_from_page_regions(src, "src.pdf", page_invoices)
    assert len(drafts) == 2
    by_supplier = {d["supplier_name"]: d for d in drafts}
    assert by_supplier["זכוכית 2000"]["reference_number"] == "24265"
    assert by_supplier["זכוכית 2000"]["total"] == "200.00"
    assert by_supplier["פיצה גראז גבעתיים"]["reference_number"] == "197705"
    assert by_supplier["פיצה גראז גבעתיים"]["total"] == "58.00"
    # לכל אחת קובץ מקור משלה
    paths = {d["source_file_path"] for d in drafts}
    assert len(paths) == 2
    for path in paths:
        assert Path(path).exists()


def test_two_receipts_from_the_same_supplier_stay_separate(tmp_path):
    """המקרה שהכי קל לערבב: אותו ספק, תאריך ומספר שונים."""
    src = tmp_path / "src.pdf"
    fitz.open().new_page(width=595, height=842).parent.save(src)
    page_invoices = [
        {"draft": app._finance_vision_invoice_to_draft(
            _entry(supplier_name="משאבות אחים אסני", reference_number="10771261",
                   invoice_date="25/08/2026", total="100.00"), src, "src.pdf"), "rect": [0, 0, 200, 400]},
        {"draft": app._finance_vision_invoice_to_draft(
            _entry(supplier_name="משאבות אחים אסני", reference_number="10770947",
                   invoice_date="19/08/2026", total="250.00"), src, "src.pdf"), "rect": [200, 0, 400, 400]},
    ]
    drafts = app._finance_drafts_from_page_regions(src, "src.pdf", page_invoices)
    refs = {d["reference_number"] for d in drafts}
    dates = {d["invoice_date"] for d in drafts}
    totals = {d["total"] for d in drafts}
    assert refs == {"10771261", "10770947"}
    assert dates == {"25/08/2026", "19/08/2026"}
    assert totals == {"100.00", "250.00"}


def test_a_missing_box_still_produces_a_row(tmp_path):
    """עדיף שורה שמצביעה על העמוד המלא מאשר חשבונית שנעלמת."""
    src = tmp_path / "src.pdf"
    fitz.open().new_page(width=595, height=842).parent.save(src)
    drafts = app._finance_drafts_from_page_regions(
        src, "src.pdf",
        [{"draft": app._finance_vision_invoice_to_draft(_entry(), src, "src.pdf"), "rect": None}],
    )
    assert len(drafts) == 1
    assert drafts[0]["source_file_path"] == str(src)


# ── בניית הטיוטה מהשדות שהמודל החזיר ─────────────────────────────────────────

def test_an_entry_without_supplier_or_amount_is_dropped(tmp_path):
    assert app._finance_vision_invoice_to_draft(
        {"supplier_name": "", "total": "", "subtotal": ""}, tmp_path / "x.pdf", "x.pdf") is None


def test_a_total_only_receipt_fills_the_subtotal(tmp_path):
    draft = app._finance_vision_invoice_to_draft(
        {"supplier_name": "חניון", "total": "20"}, tmp_path / "x.pdf", "x.pdf")
    assert draft["total"] == "20.00" and draft["subtotal"] == "20.00"


def test_amounts_survive_commas_and_shekel_signs(tmp_path):
    draft = app._finance_vision_invoice_to_draft(
        {"supplier_name": "ספק", "total": "₪1,234.50", "subtotal": "1,046.19", "vat": "188.31"},
        tmp_path / "x.pdf", "x.pdf")
    assert (draft["total"], draft["subtotal"], draft["vat"]) == ("1234.50", "1046.19", "188.31")


# ── שומר הסף האריתמטי ────────────────────────────────────────────────────────
# בהרצה בפרודקשן על הסריקה האמיתית, "זכוכית 2000" קיבלה לפני-מע"מ 49.20 ומע"מ
# 8.90 — הסכומים של הקבלה השכנה — מול סה"כ 260 משלה.

def test_parts_that_do_not_add_up_to_the_total_are_dropped(tmp_path):
    draft = app._finance_vision_invoice_to_draft(
        {"supplier_name": "זכוכית 2000", "total": "260", "subtotal": "49.20", "vat": "8.90"},
        tmp_path / "x.pdf", "x.pdf")
    assert draft["total"] == "260.00"
    assert draft["subtotal"] == "260.00"   # הושלם מהסה"כ, לא מהשכנה
    assert draft["vat"] == ""


def test_parts_that_do_add_up_are_kept(tmp_path):
    """‏49.20 + 8.90 = 58.10 מול סה"כ 58.00 — עיגול של קבלה, לא זליגה."""
    draft = app._finance_vision_invoice_to_draft(
        {"supplier_name": "פיצה גראז", "total": "58.00", "subtotal": "49.20", "vat": "8.90"},
        tmp_path / "x.pdf", "x.pdf")
    assert (draft["subtotal"], draft["vat"], draft["total"]) == ("49.20", "8.90", "58.00")


@pytest.mark.parametrize("subtotal, vat, total, kept", [
    ("100.00", "18.00", "118.00", True),
    ("100.00", "18.00", "118.90", True),    # בתוך הסבילות
    ("100.00", "18.00", "500.00", False),   # זליגה ברורה
    ("49.20",  "8.90",  "260.00", False),
    ("10.00",  "1.80",  "11.80",  True),
])
def test_tolerance_boundaries(tmp_path, subtotal, vat, total, kept):
    draft = app._finance_vision_invoice_to_draft(
        {"supplier_name": "ספק", "subtotal": subtotal, "vat": vat, "total": total},
        tmp_path / "x.pdf", "x.pdf")
    assert (draft["vat"] == vat) is kept
