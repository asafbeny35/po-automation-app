"""עמודת ימי העבודה בטבלת שעות ונוכחות.

הימים נספרים מפירוט הקובץ (תאריכים מובחנים שנרשמו בהם שעות), מתמלאים
אוטומטית בהעלאת קובץ פירוט, ומגיעים לדוח לרו"ח כ"מספר ימים לחישוב נסיעות".
"""
from __future__ import annotations

import app
from services.hr_store import HOURS_FIELDS, HOURS_HEADERS, _normalize_hours_row


def _detail(date_str, hours, status="נוכח"):
    return {"date": date_str, "hours": hours, "status": status}


# ── ספירת הימים ──────────────────────────────────────────────────────────────

def test_each_dated_row_with_hours_is_a_day():
    details = [_detail("01/08/2026", 8), _detail("02/08/2026", 7.5), _detail("03/08/2026", 4)]
    assert app._hr_work_days_from_details(details) == 3


def test_a_double_shift_day_counts_once():
    details = [_detail("01/08/2026", 4), _detail("01/08/2026", 5), _detail("02/08/2026", 8)]
    assert app._hr_work_days_from_details(details) == 2


def test_a_day_without_hours_is_not_a_travel_day():
    details = [_detail("01/08/2026", 8), _detail("02/08/2026", 0, status="חופש")]
    assert app._hr_work_days_from_details(details) == 1


def test_empty_details_mean_zero_days():
    assert app._hr_work_days_from_details([]) == 0
    assert app._hr_work_days_from_details(None) == 0


def test_a_row_without_a_date_is_ignored():
    assert app._hr_work_days_from_details([_detail("", 8)]) == 0


# ── הסכימה והנרמול ───────────────────────────────────────────────────────────

def test_work_days_sits_between_month_and_regular_hours():
    assert HOURS_FIELDS.index("work_days") == HOURS_FIELDS.index("month_key") + 1
    assert HOURS_FIELDS.index("regular_hours") == HOURS_FIELDS.index("work_days") + 1
    # הכותרות בעברית מיושרות פוזיציונית לשדות
    assert len(HOURS_HEADERS) == len(HOURS_FIELDS)
    assert HOURS_HEADERS[HOURS_FIELDS.index("work_days")] == "ימי עבודה"


def test_work_days_normalizes_to_a_whole_number():
    assert _normalize_hours_row({"work_days": "16.0"})["work_days"] == "16"
    assert _normalize_hours_row({"work_days": "21"})["work_days"] == "21"
    assert _normalize_hours_row({"work_days": ""})["work_days"] == ""
    assert _normalize_hours_row({"work_days": "לא מספר"})["work_days"] == ""


# ── הדוח לרו"ח ───────────────────────────────────────────────────────────────

def _payload(rows):
    return {"month_key": "2026-08", "month_label": "אוגוסט 2026", "rows": rows, "gross_total_label": "0.00 ₪"}


def _employee_row(**over):
    base = {
        "employee_name": "עלי כמאל סבע", "salary_rule_label": "לפי שעות",
        "gross_before_adjustments_label": "1,000.00 ₪",
        "regular_hours": 59.61, "overtime_hours": 0.0, "total_hours": 59.61,
        "work_days": "10", "warnings": [],
    }
    base.update(over)
    return base


def test_the_travel_days_line_appears_in_both_bodies():
    plain, html_body = app._hr_build_payslip_prep_email_bodies(_payload([_employee_row()]), [])
    assert "מספר ימים לחישוב נסיעות: 10" in plain
    assert "מספר ימים לחישוב נסיעות: 10" in html_body


def test_an_employee_without_days_gets_no_travel_line():
    plain, html_body = app._hr_build_payslip_prep_email_bodies(
        _payload([_employee_row(work_days="", employee_name="בן יעקב דוד")]), [])
    assert "מספר ימים לחישוב נסיעות" not in plain
    assert "מספר ימים לחישוב נסיעות" not in html_body


def test_the_parsed_hours_document_reports_its_day_count(tmp_path):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.append(["דוח שעות"])
    ws.append(["מחלקה"] + [""] * 13)
    # פורמט 1: תאריך בעמודה F, שעות בעמודה L
    for day, hours in (("01/08/2026", 8), ("02/08/2026", 7), ("02/08/2026", 2)):
        row = [""] * 14
        row[5], row[6], row[9], row[11] = day, "08:00", "16:00", hours
        ws.append(row)
    path = tmp_path / "hours.xlsx"
    wb.save(path)
    details = app._hr_parse_hours_report_rows(path)
    assert app._hr_work_days_from_details(details) == 2
