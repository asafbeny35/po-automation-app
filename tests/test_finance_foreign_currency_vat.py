"""חוק מטבע-זר במע"מ תשומות (הנחיית אסף 09.10.2026).

חשבונית שמטבעה אינו שקל לעולם לא נושאת מע"מ בחישוב — הסכום כולו הוא הבסיס.
האכיפה בנורמליזציה שכל שורה עוברת, כך שהיא תופסת גם שורות ישנות עם מע"מ
שמור וגם מסלולים שמפספסים את כלל ה-foreign בפענוח. שקל נשאר בכללים הקיימים
— הכלל הזה לא מוסיף מע"מ לשום שורה, רק מונע אותו ממטבע זר.
"""
from __future__ import annotations

import pytest

import app


def _row(**overrides):
    base = {
        "row_id": "finance-upload-test",
        "invoice_date": "01/10/2026",
        "supplier_name": "ספק כלשהו",
        "service_or_product": "שירות",
        "subtotal": "",
        "vat": "",
        "total": "",
        "currency_code": "ILS",
    }
    base.update(overrides)
    return base


# ── מטבע זר: מע"מ מאופס תמיד ─────────────────────────────────────────────────

@pytest.mark.parametrize("currency", ["USD", "EUR", "GBP"])
def test_foreign_currency_vat_is_always_zeroed(currency):
    normalized = app._normalize_finance_invoice_row_app(
        _row(currency_code=currency, subtotal="84.75", vat="15.25", total="100.00")
    )
    assert normalized["vat"] == "0.00"
    assert normalized["total"] == "100.00"
    # הסכום כולו הוא הבסיס — אין רכיב מע"מ
    assert normalized["subtotal"] == "100.00"


def test_foreign_row_without_total_gets_it_from_the_parts():
    normalized = app._normalize_finance_invoice_row_app(
        _row(currency_code="USD", subtotal="84.75", vat="15.25", total="")
    )
    assert normalized["vat"] == "0.00"
    assert normalized["subtotal"] == "100.00"
    assert normalized["total"] == "100.00"


def test_foreign_row_with_no_vat_stays_clean():
    normalized = app._normalize_finance_invoice_row_app(
        _row(currency_code="USD", subtotal="100.00", vat="", total="100.00")
    )
    assert normalized["vat"] == "0.00"
    assert normalized["subtotal"] == "100.00"
    assert normalized["total"] == "100.00"


def test_imputation_never_invents_vat_for_foreign_currency():
    """גם מסלול הגזירה-מהסה"כ לא ממציא 18% לחשבונית במטבע זר."""
    row = app._finance_impute_vat_from_total_if_needed(
        _row(currency_code="EUR", subtotal="", vat="", total="236.00"), text_cache={}
    )
    assert row["vat"] == "0.00"
    assert row["total"] == "236.00"


# ── שקל: הכללים הקיימים לא משתנים ────────────────────────────────────────────

def test_ils_row_keeps_its_printed_vat():
    normalized = app._normalize_finance_invoice_row_app(
        _row(currency_code="ILS", subtotal="100.00", vat="18.00", total="118.00")
    )
    assert normalized["vat"] == "18.00"
    assert normalized["subtotal"] == "100.00"


def test_missing_currency_defaults_to_ils_and_keeps_vat():
    normalized = app._normalize_finance_invoice_row_app(
        _row(currency_code="", subtotal="100.00", vat="18.00", total="118.00")
    )
    assert normalized["currency_code"] == "ILS"
    assert normalized["vat"] == "18.00"


def test_the_rule_never_adds_vat_to_ils_rows():
    """"זה לא אומר שתמיד כן להוסיף מע"מ אם זה שקל" — שורה שקלית בלי מע"מ
    נשארת בלי מע"מ בנורמליזציה (הגזירה היא החלטה נפרדת במסלול שלה)."""
    normalized = app._normalize_finance_invoice_row_app(
        _row(currency_code="ILS", subtotal="100.00", vat="", total="100.00")
    )
    assert normalized["vat"] == ""
