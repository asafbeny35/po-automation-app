"""צירוף אישור ניכוי מס וניהול ספרים לאישורי מסירה.

מהיום כל מייל אישור מסירה מצרף את האישור כברירת מחדל (צ'קבוקס במודאל),
והמערכת רושמת פר לקוח שהאישור כבר נשלח כדי להציג הודעה מהשליחה השנייה.
"""
from __future__ import annotations

import fitz
import pytest

import app


# ── המסמך עצמו ───────────────────────────────────────────────────────────────

def test_the_certificate_has_two_pages_and_the_new_first_page():
    """עמוד 1 הוחלף בהדפסה מ-07/09/2026; עמוד 2 (ניהול פנקסים) נשאר."""
    spec = app.ADMIN_DRIVE_ASSETS["business-tax-books"]
    doc = fitz.open(spec["local_path"])
    assert doc.page_count == 2
    assert "07/09/2026" in doc[0].get_text()
    assert "ניהול פנקסי חשבונות" in doc[1].get_text()


# ── רישום "כבר נשלח" פר לקוח ─────────────────────────────────────────────────

def _customers():
    return [
        {"customer_name": "י.א אלון בניה בע״מ", "tax_certificate_sent": ""},
        {"customer_name": "טובול ציוד וחומרי בניין", "tax_certificate_sent": ""},
    ]


def test_marking_sets_the_flag_only_on_the_matching_customer(monkeypatch):
    saved = {}
    monkeypatch.setattr(app, "load_customer_rows", _customers)
    monkeypatch.setattr(app, "load_inactive_customer_rows", lambda: [])
    monkeypatch.setattr(app, "save_customer_rows", lambda rows: saved.update(active=rows))
    monkeypatch.setattr(app, "save_inactive_customer_rows", lambda rows: saved.update(inactive=rows))

    assert app._mark_customer_tax_certificate_sent("י.א אלון בניה בע״מ") is True
    by_name = {r["customer_name"]: r for r in saved["active"]}
    assert by_name["י.א אלון בניה בע״מ"]["tax_certificate_sent"] == "TRUE"
    assert by_name["טובול ציוד וחומרי בניין"]["tax_certificate_sent"] == ""


def test_an_unknown_customer_changes_nothing(monkeypatch):
    monkeypatch.setattr(app, "load_customer_rows", _customers)
    monkeypatch.setattr(app, "load_inactive_customer_rows", lambda: [])
    calls = []
    monkeypatch.setattr(app, "save_customer_rows", lambda rows: calls.append(rows))
    monkeypatch.setattr(app, "save_inactive_customer_rows", lambda rows: calls.append(rows))
    assert app._mark_customer_tax_certificate_sent("לקוח שאינו קיים") is False
    assert not calls


def test_the_bank_flag_still_uses_its_own_field(monkeypatch):
    """הרפקטור לפונקציה משותפת לא ערבב בין שני הדגלים."""
    saved = {}
    monkeypatch.setattr(app, "load_customer_rows", _customers)
    monkeypatch.setattr(app, "load_inactive_customer_rows", lambda: [])
    monkeypatch.setattr(app, "save_customer_rows", lambda rows: saved.update(active=rows))
    monkeypatch.setattr(app, "save_inactive_customer_rows", lambda rows: saved.update(inactive=rows))
    assert app._mark_customer_bank_details_updated("טובול ציוד וחומרי בניין") is True
    by_name = {r["customer_name"]: r for r in saved["active"]}
    assert by_name["טובול ציוד וחומרי בניין"]["bank_details_updated_sent"] == "TRUE"
    assert by_name["טובול ציוד וחומרי בניין"].get("tax_certificate_sent", "") == ""


# ── הסכימה ───────────────────────────────────────────────────────────────────

def test_the_customer_schema_knows_the_new_field():
    from services import google_sheets
    assert "tax_certificate_sent" in google_sheets.CUSTOMER_FIELDS
