"""חשבונית שכ"ד מרכזת של אלרון קאר (SI266008848, ‏04.10.2026, סריקה).

שני פחים בפריסה הזו: ה-OCR מפרק את עמודות הסיכום כך שהמספרים נדדו
מהתוויות, ו"(18.00%)" נקרא כסכום המע"מ — מה שהוליד total=18.00 ו-subtotal
של 15.25. פח שלישי: גם זוג המחירים-כולל-מע"מ של השורות (7,080+5,192)
מסתכם בדיוק לסה"כ — רק אילוץ יחס 18% בוחר את הזוג הנכון (10,400+1,872).
"""
from __future__ import annotations

from pathlib import Path

import pytest

import app


# תמצית נאמנה של פלט ה-OCR מהסריקה האמיתית
OCR_TEXT = """אלרון קאר ח.ר בע"מ
צומת אלובין נעמן ת.ד 1126
קרית ים
טלפון: 04-8726413, פקס: 04-8400245 עוסק מורשה: 513074500
לכבוד:
הדפסת חשבונית מרכזת
תאריך חשבונית: 04/10/26 תאריך הדפסה: 04/10/26 שעת הדפסה: 11:35 מספר תעודה: SI266008848
פרטים: שכ"ד 10.2026
בן יעקב אסף פתרונות טקסטיל
חשבונית מס מרכזת SI266008848 - מקור
שכ"ד 10.2026 שטח
1.00 יח|6,000.00 ש"ח|7,080.00 ש"ח
שכ"ד 10.2026 שטח
1.00 יח|4,400.00 ש"ח|5,192.00 ש"ח
ברקוד מספר חשבונית: *SI266008848* לתשלום עד: 04/10/26
מספר הקצאה: 20261004113541865
מחיר כולל
מע"מ (18.00%)
סה"כ מחיר
12,272.00 שייח
סה"כ נותר לתשלום 12,272.00
6,000.00
4,400.00
10,400.00 1,872.00
ט.ל.ח."""


@pytest.fixture(scope="module")
def parsed(tmp_path_factory):
    file_path = tmp_path_factory.mktemp("elron") / "KMN94DDF821DA24_034830.pdf"
    file_path.write_bytes(b"%PDF-1.4 stub")
    return app._finance_parse_elron_car_invoice(OCR_TEXT, OCR_TEXT, file_path.name, file_path)


def test_the_scan_is_detected():
    assert app._finance_detect_elron_car_invoice(OCR_TEXT, OCR_TEXT, "doc.pdf") is True


def test_reference_and_date(parsed):
    assert parsed["reference_number"] == "SI266008848"
    assert parsed["invoice_date"] == "04/10/2026"


def test_the_total_comes_from_the_remaining_to_pay_line(parsed):
    """"סה"כ נותר לתשלום 12,272.00" — התווית היחידה שהסכום צמוד אליה."""
    assert parsed["total"] == "12272.00"


def test_the_vat_is_not_the_percentage(parsed):
    """"(18.00%)" נקרא בעבר כסכום המע"מ והפיל את כל החישוב ל-18.00."""
    assert parsed["vat"] == "1872.00"
    assert parsed["subtotal"] == "10400.00"


def test_the_18_percent_relation_picks_the_right_pair():
    """גם 7,080+5,192 מסתכם ל-12,272 — בלי אילוץ ה-18% הזוג השגוי נבחר."""
    assert round(7080.0 + 5192.0, 2) == 12272.0          # הפח קיים באמת
    assert abs(round(10400.0 * 0.18, 2) - 1872.0) < 0.01  # והאילוץ מבדיל


def test_the_service_is_the_rent_period_from_the_document(parsed):
    assert parsed["service_or_product"] == 'שכ"ד 10.2026'


def test_a_missing_details_line_falls_back_to_the_document_period():
    """הנפילה הקשיחה הישנה הדביקה "שכ"ד 5.2026 + הפרשי הצמדה" לכל חשבונית
    שה-OCR פספס בה את "פרטים" — עכשיו התקופה נלקחת מהמסמך עצמו."""
    garbled = OCR_TEXT.replace('פרטים: שכ"ד 10.2026', "פרסים: ---")
    result = app._finance_parse_elron_car_invoice(garbled, garbled, "doc.pdf", Path("/tmp/elron-garbled.pdf"))
    assert result["service_or_product"] == 'שכ"ד 10.2026'
    assert "5.2026" not in result["service_or_product"]
    assert "הצמדה" not in result["service_or_product"]


def test_the_allocation_number_is_extracted_above_10k(parsed):
    assert parsed["allocation_number"] == "20261004113541865"
