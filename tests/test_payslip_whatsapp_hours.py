"""שליחת תלוש בוואטסאפ עם דוח הנוכחות כמסמך אחד רצוף.

הצ'קבוקס במודאל מסומן כברירת מחדל; כשהוא כבוי נשלח רק התלוש, וכשאין דוח
שעות לחודש נשלח התלוש לבד עם אזהרה — לא נכשלת השליחה כולה.
"""
from __future__ import annotations

import fitz
import pytest

import app


def _detail(date_str, hours, entry="08:00", exit_time="16:00"):
    return {"date": date_str, "day_name": "א", "entry_time": entry, "exit_time": exit_time,
            "time_range": f"{entry}-{exit_time}", "hours": hours, "status": "נוכח"}


def _payslip(tmp_path):
    path = tmp_path / "תלוש.pdf"
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    doc.save(path)
    return path


# ── דף הנוכחות ───────────────────────────────────────────────────────────────

def test_the_attendance_pdf_carries_every_day_and_the_summary():
    pdf_bytes = app._hr_hours_attendance_pdf_bytes(
        "תאי יונתן גורן", "2026-07",
        [_detail("01/07/2026", 7.33), _detail("02/07/2026", 5.27)],
    )
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = doc[0].get_text()
    assert "01/07/2026" in text and "02/07/2026" in text
    assert "7.33" in text and "5.27" in text
    assert "12.60" in text            # שורת הסיכום
    assert "08:00-16:00" in text


# ── המיזוג למסמך אחד ─────────────────────────────────────────────────────────

def _target_row():
    return {"employee_id": "emp_x", "month_key": "2026-07", "employee_name": "עובד בדיקה"}


def _with_hours(monkeypatch, tmp_path):
    monkeypatch.setattr(app, "_hr_find_hours_row", lambda *a: {"row_id": "h1"})
    monkeypatch.setattr(app, "_hr_resolve_hours_attachment", lambda row: {"available": True, "path": str(tmp_path / "hours.xlsx")})
    monkeypatch.setattr(app, "_hr_parse_hours_report_rows", lambda p: [_detail("01/07/2026", 8)])
    monkeypatch.setattr(app, "load_hr_rows", lambda kind: [])


def test_the_merged_document_is_payslip_then_attendance(tmp_path, monkeypatch):
    _with_hours(monkeypatch, tmp_path)
    monkeypatch.setattr(app, "_build_hr_installations_payload", lambda: {"months": []})

    merged = app._hr_payslip_with_hours_pdf(_payslip(tmp_path), _target_row())
    assert merged is not None
    assert merged.name == "תלוש שכר ונוכחות - עובד בדיקה - 2026-07.pdf"
    doc = fitz.open(merged)
    assert doc.page_count == 2       # עמוד תלוש + עמוד נוכחות
    assert "01/07/2026" in doc[1].get_text()
    doc.close()
    merged.unlink()


def test_an_employee_with_installations_gets_a_third_page(tmp_path, monkeypatch):
    """עלי: תלוש + נוכחות + התקנות החודש — שלושה עמודים במסמך אחד."""
    _with_hours(monkeypatch, tmp_path)
    monkeypatch.setattr(app, "_build_hr_installations_payload", lambda: {
        "door_rate": 14.0,
        "months": [{
            "month_key": "2026-07", "employee_id": "emp_x", "employee_name": "עובד בדיקה",
            "label": "התקנות יולי 2026", "include_in_payroll": True,
            "rows": [{"install_date": "01/07/2026", "installed_quantity": 46,
                      "doors_amount": 644.0, "food": 150.0, "fuel": 450.0,
                      "advance": 880.0, "total": 364.0}],
            "totals": {"installed_quantity": 46, "doors_amount": 644.0, "food": 150.0,
                       "fuel": 450.0, "advance": 880.0, "total": 364.0},
        }],
    })

    merged = app._hr_payslip_with_hours_pdf(_payslip(tmp_path), _target_row())
    doc = fitz.open(merged)
    assert doc.page_count == 3
    assert "01/07/2026" in doc[2].get_text()
    doc.close()
    merged.unlink()


def test_a_broken_installations_build_does_not_block_the_send(tmp_path, monkeypatch):
    def _boom():
        raise RuntimeError("installations payload unavailable")
    _with_hours(monkeypatch, tmp_path)
    monkeypatch.setattr(app, "_build_hr_installations_payload", _boom)
    merged = app._hr_payslip_with_hours_pdf(_payslip(tmp_path), _target_row())
    assert merged is not None and fitz.open(merged).page_count == 2
    merged.unlink()


def test_without_an_hours_report_the_merge_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "_hr_find_hours_row", lambda *a: None)
    monkeypatch.setattr(app, "load_hr_rows", lambda kind: [])
    assert app._hr_payslip_with_hours_pdf(_payslip(tmp_path), _target_row()) is None


def test_an_unavailable_attachment_also_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "_hr_find_hours_row", lambda *a: {"row_id": "h1"})
    monkeypatch.setattr(app, "_hr_resolve_hours_attachment", lambda row: {"available": False})
    monkeypatch.setattr(app, "load_hr_rows", lambda kind: [])
    assert app._hr_payslip_with_hours_pdf(_payslip(tmp_path), _target_row()) is None
