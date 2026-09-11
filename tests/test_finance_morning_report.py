"""דוח ההכנסות ממורנינג לתקופת הדיווח + ההצלבה מול סיכום המע"מ.

הדיווח דו-חודשי: דיווח 15/09 מכסה 01/07–31/08. הדוח כולל חשבוניות מס
(305/320) וחשבוניות זיכוי (330, בסכומים שליליים) — קבלות לא. מ-10.09 שורת
הסיכום עצמה מקזזת זיכויים, ולכן ההצלבה משווה נטו מול נטו.
"""
from __future__ import annotations

import asyncio
from datetime import date

import fitz
import pytest

import app


def _doc(number, doc_date, vat, total, type_code="305", customer="לקוח"):
    return {
        "number": number, "date": doc_date, "type_code": type_code,
        "type": "", "customer_name": customer, "amount": total,
        "raw": {"vat": vat, "amount": total},
    }


# ── סיווג המסמכים ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("code, kind", [("305", "invoice"), ("320", "invoice"), ("330", "credit")])
def test_type_codes_map_to_report_kinds(code, kind):
    assert app._finance_morning_report_doc_kind({"type_code": code, "type": ""}) == kind


def test_a_plain_receipt_is_not_a_vat_document():
    assert app._finance_morning_report_doc_kind({"type_code": "400", "type": "קבלה"}) == ""


def test_hebrew_type_text_works_without_a_code():
    assert app._finance_morning_report_doc_kind({"type_code": "", "type": "חשבונית מס"}) == "invoice"
    assert app._finance_morning_report_doc_kind({"type_code": "", "type": "חשבונית זיכוי"}) == "credit"


# ── התקופה וההצלבה ───────────────────────────────────────────────────────────

def _run_report(monkeypatch, docs, summary_rows):
    async def fake_docs():
        return docs
    async def fake_summary(due_dates):
        return summary_rows
    monkeypatch.setattr(app, "_fetch_finance_prod_income_documents", fake_docs)
    monkeypatch.setattr(app, "_finance_vat_summary_rows_for_due_dates", fake_summary)
    return asyncio.run(app._finance_morning_income_report_for_due_dates(["15/09/2026"]))


def test_september_report_covers_july_and_august_only(monkeypatch):
    docs = [
        _doc("1", "2026-06-30", 100, 700),   # לפני התקופה
        _doc("2", "2026-07-01", 90, 600),    # יום ראשון בתקופה
        _doc("3", "2026-08-31", 80, 500),    # יום אחרון בתקופה
        _doc("4", "2026-09-01", 70, 400),    # אחרי התקופה
    ]
    report = _run_report(monkeypatch, docs, [{"due_date": "15/09/2026", "vat_payable": 170.0, "vat_credit": 0, "vat_due": 170.0}])
    period = report["periods"][0]
    assert period["period_start"] == "01/07/2026"
    assert period["period_end"] == "31/08/2026"
    assert [r["number"] for r in period["rows"]] == ["2", "3"]


def test_credits_are_negative_and_reported_separately(monkeypatch):
    docs = [
        _doc("10", "2026-07-05", 180, 1180),
        _doc("11", "2026-07-20", 90, 590, type_code="330"),
    ]
    report = _run_report(monkeypatch, docs, [{"due_date": "15/09/2026", "vat_payable": 180.0, "vat_credit": 0, "vat_due": 180.0}])
    period = report["periods"][0]
    credit_row = next(r for r in period["rows"] if r["kind"] == "credit")
    assert credit_row["vat"] == -90.0 and credit_row["total"] == -590.0
    assert period["invoices_vat"] == 180.0
    assert period["credits_vat"] == -90.0
    assert period["vat_sum"] == 90.0


def test_reconciliation_matches_when_net_vat_equals_summary(monkeypatch):
    docs = [_doc("10", "2026-07-05", 180, 1180), _doc("11", "2026-08-01", 20, 120)]
    report = _run_report(monkeypatch, docs, [{"due_date": "15/09/2026", "vat_payable": 200.0, "vat_credit": 50.0, "vat_due": 150.0}])
    period = report["periods"][0]
    assert period["reconciliation_matched"] is True
    assert period["summary_vat_due"] == 150.0


def test_with_credits_the_summary_must_be_net_to_match(monkeypatch):
    """הסיכום מקזז זיכויים — סיכום שמציג רק את צד החשבוניות נחשב פער."""
    docs = [
        _doc("10", "2026-07-05", 180, 1180),
        _doc("11", "2026-07-20", 90, 590, type_code="330"),
    ]
    net_summary = [{"due_date": "15/09/2026", "vat_payable": 90.0, "vat_credit": 0, "vat_due": 90.0}]
    gross_summary = [{"due_date": "15/09/2026", "vat_payable": 180.0, "vat_credit": 0, "vat_due": 180.0}]
    assert _run_report(monkeypatch, docs, net_summary)["periods"][0]["reconciliation_matched"] is True
    mismatch = _run_report(monkeypatch, docs, gross_summary)["periods"][0]
    assert mismatch["reconciliation_matched"] is False
    assert mismatch["reconciliation_diff"] == -90.0


def test_reconciliation_flags_a_gap(monkeypatch):
    docs = [_doc("10", "2026-07-05", 180, 1180)]
    report = _run_report(monkeypatch, docs, [{"due_date": "15/09/2026", "vat_payable": 200.0, "vat_credit": 0, "vat_due": 200.0}])
    period = report["periods"][0]
    assert period["reconciliation_matched"] is False
    assert period["reconciliation_diff"] == -20.0
    lines = app._finance_morning_reconciliation_lines(report)
    assert any("פער" in line for line in lines)


# ── ה-PDF הרציף ──────────────────────────────────────────────────────────────

def test_the_pdf_carries_documents_totals_and_reconciliation(monkeypatch):
    docs = [
        _doc("550621", "2026-08-27", 3024.0, 19824.0, customer="סלע ביצוע"),
        _doc("750040", "2026-08-30", 118.8, 778.8, type_code="330", customer="ליפמן"),
    ]
    report = _run_report(monkeypatch, docs, [{"due_date": "15/09/2026", "vat_payable": 3024.0, "vat_credit": 100.0, "vat_due": 2924.0}])
    pdf = app._build_finance_morning_income_pdf(report)
    doc = fitz.open(stream=pdf, filetype="pdf")
    text = "".join(page.get_text() for page in doc)
    assert "550621" in text and "750040" in text
    assert "3,024.00" in text
    assert "-118.80" in text or "118.80-" in text
    assert "2,924.00" in text          # נותר לתשלום מהסיכום


def test_an_empty_period_still_renders_a_document(monkeypatch):
    report = _run_report(monkeypatch, [], [{"due_date": "15/09/2026", "vat_payable": 0, "vat_credit": 0, "vat_due": 0}])
    pdf = app._build_finance_morning_income_pdf(report)
    assert fitz.open(stream=pdf, filetype="pdf").page_count >= 1


# ── מע"מ תשומות אסור: חו"ל וחיובים עירוניים (הערת הרו"ח 10.09) ────────────────

@pytest.mark.parametrize("supplier, service, currency, reason", [
    ("Kapwing, Inc.", "subscription", "USD", "foreign"),
    ("Supabase", "compute", "USD", "foreign"),
    ("Runway AI, Inc.", "credits", "", "foreign"),          # סיומת Inc בלי מטבע
    ("עיריית תל אביב-יפו", "חשבון ארנונה כללית", "ILS", "municipal"),
    ("מועצה אזורית חוף הכרמל", "חשבון מים וביוב", "ILS", "municipal"),
    ("מי אביבים", "חשבון מים וביוב 7-8/2026", "ILS", "municipal"),
    ("פלציב עין הנציב", "יריעות", "ILS", ""),               # ספק ישראלי רגיל
    ("פרטנר תקשורת בע״מ", "סלולר", "ILS", ""),
])
def test_disallowed_vat_reasons(supplier, service, currency, reason):
    assert app._finance_vat_disallowed_reason(supplier, service, currency) == reason


def test_a_foreign_invoice_draft_gets_no_vat(tmp_path):
    draft = app._finance_vision_invoice_to_draft(
        {"supplier_name": "Vercel Inc.", "subtotal": "20.00", "vat": "3.05", "total": "23.05", "currency": "USD"},
        tmp_path / "x.pdf", "x.pdf")
    assert draft["vat"] == "0.00" or draft["vat"] == ""
    assert draft["subtotal"] == draft["total"]


def test_an_arnona_draft_gets_no_vat(tmp_path):
    draft = app._finance_vision_invoice_to_draft(
        {"supplier_name": "עיריית תל אביב-יפו", "service_or_product": "חשבון ארנונה כללית",
         "subtotal": "430.47", "vat": "77.49", "total": "507.96", "currency": "ILS"},
        tmp_path / "x.pdf", "x.pdf")
    assert app._finance_parse_number(draft["vat"]) == 0
    assert draft["subtotal"] == draft["total"]


def test_imputation_never_invents_vat_for_disallowed_rows():
    """זה המנגנון שהחזיר את המע"מ אחרי כל איפוס — חייב להישאר חסום."""
    row = {"supplier_name": "עיריית תל אביב-יפו", "service_or_product": "ארנונה",
           "invoice_date": "16/08/2026", "subtotal": "507.96", "vat": "0.00",
           "total": "507.96", "currency_code": "ILS"}
    result = app._finance_impute_vat_from_total_if_needed(row)
    assert app._finance_parse_number(result["vat"]) == 0


def test_imputation_still_blocked_for_foreign_currency():
    row = {"supplier_name": "Supabase", "service_or_product": "compute",
           "invoice_date": "18/08/2026", "subtotal": "98.07", "vat": "",
           "total": "98.07", "currency_code": "USD"}
    result = app._finance_impute_vat_from_total_if_needed(row)
    assert app._finance_parse_number(result["vat"]) == 0
