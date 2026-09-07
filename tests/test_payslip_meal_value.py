"""שווי ארוחות במודאל התלושים להפקה.

הסכום נמשך מחשבונית הסיבוס האחרונה של פלאקסי ישראל ומתחלק שווה בשווה בין
מלכה בן יעקב ודוד בן יעקב בלבד. הבדיקות מכסות את בחירת החשבונית (עדיפות
לחודש הנבחר), את החלוקה באגורות, ואת בניית המייל — כולל שהרכיב לא מופיע
כשלא סומן הצ'קבוקס.
"""
from __future__ import annotations

import pytest

import app


def _invoice(date_str, total, ref="SI1", supplier='פלאקסי ישראל בע"מ'):
    return {"supplier_name": supplier, "invoice_date": date_str, "total": total, "reference_number": ref}


def _with_invoices(monkeypatch, rows):
    monkeypatch.setattr(app, "load_marketing_rows", lambda kind, **kw: rows)
    monkeypatch.setattr(app, "_dedupe_finance_invoice_rows", lambda rows: rows)


# ── בחירת החשבונית ───────────────────────────────────────────────────────────

def test_the_invoice_of_the_selected_month_wins(monkeypatch):
    _with_invoices(monkeypatch, [
        _invoice("31/07/2026", "1796.00", "SI-JUL"),
        _invoice("31/08/2026", "1385.00", "SI-AUG"),
    ])
    picked = app._hr_meal_value_invoice("2026-07")
    assert picked["reference_number"] == "SI-JUL"
    assert picked["amount"] == 1796.0
    assert picked["in_selected_month"] is True


def test_without_a_matching_month_the_latest_invoice_is_used(monkeypatch):
    _with_invoices(monkeypatch, [
        _invoice("31/07/2026", "1796.00", "SI-JUL"),
        _invoice("31/08/2026", "1385.00", "SI-AUG"),
    ])
    picked = app._hr_meal_value_invoice("2026-09")
    assert picked["reference_number"] == "SI-AUG"
    assert picked["in_selected_month"] is False


def test_other_suppliers_are_ignored(monkeypatch):
    _with_invoices(monkeypatch, [
        _invoice("31/08/2026", "9999.00", "SI-X", supplier="ספק אחר בע\"מ"),
    ])
    assert app._hr_meal_value_invoice("2026-08") == {"found": False}


def test_a_zero_amount_invoice_is_skipped(monkeypatch):
    _with_invoices(monkeypatch, [
        _invoice("31/08/2026", "0", "SI-ZERO"),
        _invoice("31/07/2026", "1796.00", "SI-JUL"),
    ])
    picked = app._hr_meal_value_invoice("2026-08")
    assert picked["reference_number"] == "SI-JUL"


def test_a_broken_cache_returns_not_found(monkeypatch):
    def _boom(kind, **kw):
        raise RuntimeError("cache unavailable")
    monkeypatch.setattr(app, "load_marketing_rows", _boom)
    assert app._hr_meal_value_invoice("2026-08") == {"found": False}


# ── החלוקה בין מלכה ודוד ─────────────────────────────────────────────────────

def test_an_even_amount_splits_in_half():
    shares = app._hr_meal_value_split(1385.00)
    assert [(s["employee_name"], s["amount"]) for s in shares] == [
        ("מלכה בן יעקב", 692.5),
        ("דוד בן יעקב", 692.5),
    ]


def test_an_odd_agora_goes_to_malka_and_the_sum_stays_exact():
    shares = app._hr_meal_value_split(100.01)
    assert shares[0]["employee_name"] == "מלכה בן יעקב"
    assert shares[0]["amount"] == 50.01
    assert shares[1]["amount"] == 50.0
    assert round(shares[0]["amount"] + shares[1]["amount"], 2) == 100.01


def test_only_malka_and_david_are_in_the_split():
    names = {s["employee_name"] for s in app._hr_meal_value_split(500)}
    assert names == {"מלכה בן יעקב", "דוד בן יעקב"}


# ── המייל לרו"ח ──────────────────────────────────────────────────────────────

def _employee_email_row(employee_id, name):
    return {
        "employee_id": employee_id, "employee_name": name,
        "salary_rule_label": "שכר גלובלי", "gross_before_adjustments_label": "10,000.00 ₪",
        "regular_hours": 0.0, "overtime_hours": 0.0, "total_hours": 0.0,
        "work_days": "", "warnings": [],
    }


def _payload(rows=None):
    return {"month_key": "2026-08", "month_label": "אוגוסט 2026", "rows": rows or [], "gross_total_label": "0.00 ₪"}


def _meal(total=1385.0):
    return {
        "total": total,
        "total_label": f"{total:,.2f} ₪",
        "source_label": "לפי חשבונית פלאקסי SI266113793 מ-31/08/2026",
        "shares": app._hr_meal_value_split(total),
    }


def test_the_meal_share_sits_inside_each_employee_component():
    rows = [
        _employee_email_row("emp_david_ben_yacov", "בן יעקב דוד"),
        _employee_email_row("emp_malka_ben_yacov", "בן יעקב מלכה"),
        _employee_email_row("emp_solomon_shibshi", "שיבשי סלומון"),
    ]
    plain, html_body = app._hr_build_payslip_prep_email_bodies(_payload(rows), [], meal_value=_meal())
    # בתוך רכיב העובד — לא כקוביה נפרדת בסוף
    assert "  שווי ארוחות (סיבוס): 692.50 ₪" in plain
    assert 'שווי ארוחות (סיבוס): 692.50 ₪' in html_body
    assert "סה״כ לחלוקה" not in html_body
    assert "SI266113793" in plain and "SI266113793" in html_body
    # סלומון לא מקבל שורת שווי ארוחות
    solomon_block = plain.split("שיבשי סלומון", 1)[1]
    assert "שווי ארוחות" not in solomon_block.split("- ")[0]


def test_a_share_without_a_matching_employee_still_reaches_the_mail():
    """עובד הושבת או שונה שמו — הנתח לא נבלע בשקט."""
    plain, html_body = app._hr_build_payslip_prep_email_bodies(_payload([]), [], meal_value=_meal())
    for body in (plain, html_body):
        assert "מלכה בן יעקב" in body and "דוד בן יעקב" in body
        assert "692.50" in body


def test_without_the_flag_no_meal_section_is_added():
    plain, html_body = app._hr_build_payslip_prep_email_bodies(_payload(), [])
    assert "ארוחות" not in plain
    assert "ארוחות" not in html_body


def test_a_manually_edited_amount_is_labelled_as_manual():
    meal = {
        "total": 1200.0,
        "total_label": "1,200.00 ₪",
        "source_label": "סכום שהוזן ידנית",
        "shares": app._hr_meal_value_split(1200.0),
    }
    plain, _ = app._hr_build_payslip_prep_email_bodies(_payload(), [], meal_value=meal)
    assert "סכום שהוזן ידנית" in plain
    assert "600.00" in plain
