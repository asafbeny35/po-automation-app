"""שער חודש-בעיצומו לדוחות שעות.

המקרה של יונתן (08.10.2026): הייצוא מהשעון נעשה על אוקטובר-עד-היום (יומיים)
במקום על ספטמבר, והמערכת שמרה אותו בשקט תחת אוקטובר. דוח שעות חודשי תקף רק
לחודש שהסתיים — חודש-בעיצומו נדחה עם הסבר, וקובץ שתוכנו סותר את החודש שנבחר
ידנית נדחה גם הוא.
"""
from __future__ import annotations

from datetime import date

from unittest.mock import patch

import pytest

import app


def _details(month: str, days: int):
    return [
        {"date": f"{day:02d}/{month}", "hours": 5.0}
        for day in range(1, days + 1)
    ]


# ── העוזר ────────────────────────────────────────────────────────────────────

def test_a_finished_month_passes():
    assert app._hr_hours_month_in_progress_error("יונתן", "2026-09", _details("09/2026", 10)) == ""


def test_the_current_month_is_rejected_with_an_explanation():
    current = date.today().strftime("%Y-%m")
    message = app._hr_hours_month_in_progress_error("תאי יונתן גורן", current, _details(current[5:] + "/" + current[:4], 2))
    assert "שעדיין לא הסתיים" in message
    assert "תאי יונתן גורן" in message
    assert "2 ימי עבודה" in message


def test_a_future_month_is_rejected():
    assert app._hr_hours_month_in_progress_error("עלי", "2099-01") != ""


def test_garbage_month_key_is_ignored():
    assert app._hr_hours_month_in_progress_error("עלי", "") == ""
    assert app._hr_hours_month_in_progress_error("עלי", "10/2026") == ""


# ── הזרימה האוטומטית (hr-ingest-files) ──────────────────────────────────────

def _employee():
    return {"employee_id": "emp_cf3efc2c79", "full_name": "תאי יונתן גורן", "employment_type": "hourly"}


def test_ingest_rejects_an_in_progress_month(client, tmp_path):
    current = date.today().strftime("%Y-%m")
    parsed = {
        "doc_type": "hours",
        "employee": _employee(),
        "month_key": current,
        "regular_hours": "9.96",
        "overtime_hours": "0.00",
        "work_days": "2",
        "details": [{"date": f"01/{current[5:]}/{current[:4]}", "hours": 4.23}],
        "text": "",
    }
    with (
        patch("app.load_hr_rows", side_effect=lambda kind: [_employee()] if kind == "employees" else []),
        patch("app._hr_parse_payslip_document", return_value=None),
        patch("app._hr_parse_contribution_document", return_value=None),
        patch("app._hr_parse_contribution_proof_document", return_value=None),
        patch("app._hr_parse_hours_document", return_value=parsed),
        patch("app._hr_storage_dir", return_value=tmp_path),
        patch("app._hr_upload_file_to_drive") as drive_mock,
        patch("app.upsert_hr_row") as upsert_mock,
    ):
        resp = client.post(
            "/hr-ingest-files",
            files={"files": ("monthHour(יונתן תאי).xlsx", b"stub", "application/vnd.ms-excel")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("errors"), "חייבת להופיע שגיאה על חודש-בעיצומו"
    assert "שעדיין לא הסתיים" in data["errors"][0]["error"]
    drive_mock.assert_not_called()
    upsert_mock.assert_not_called()


def test_ingest_accepts_a_finished_month(client, tmp_path):
    parsed = {
        "doc_type": "hours",
        "employee": _employee(),
        "month_key": "2026-09",
        "regular_hours": "100.00",
        "overtime_hours": "0.00",
        "work_days": "20",
        "details": [{"date": "01/09/2026", "hours": 5.0}],
        "text": "",
    }
    with (
        patch("app.load_hr_rows", side_effect=lambda kind: [_employee()] if kind == "employees" else []),
        patch("app._hr_parse_payslip_document", return_value=None),
        patch("app._hr_parse_contribution_document", return_value=None),
        patch("app._hr_parse_contribution_proof_document", return_value=None),
        patch("app._hr_parse_hours_document", return_value=parsed),
        patch("app._hr_storage_dir", return_value=tmp_path),
        patch("app._hr_upload_file_to_drive", return_value={"drive_file_id": "x", "drive_url": "y"}),
        patch("app.upsert_hr_row") as upsert_mock,
    ):
        resp = client.post(
            "/hr-ingest-files",
            files={"files": ("monthHour(יונתן תאי).xlsx", b"stub", "application/vnd.ms-excel")},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert not data.get("errors")
    assert any(r.get("section") == "hours" and r.get("month_key") == "2026-09" for r in data.get("results") or [])
    assert upsert_mock.called


# ── ההעלאה הידנית (hr-upload-file) ───────────────────────────────────────────

def test_manual_upload_rejects_a_content_month_mismatch(client, tmp_path):
    details = [{"date": "01/09/2026", "hours": 5.0}]
    with (
        patch("app.load_hr_rows", side_effect=lambda kind: [_employee()] if kind == "employees" else []),
        patch("app._hr_storage_dir", return_value=tmp_path),
        patch("app._hr_parse_hours_report_rows", return_value=details),
        patch("app._hr_upload_file_to_drive") as drive_mock,
    ):
        resp = client.post(
            "/hr-upload-file",
            data={"employee_id": "emp_cf3efc2c79", "section": "hours", "month_key": "2026-10"},
            files={"file": ("hours.xlsx", b"stub", "application/vnd.ms-excel")},
        )
    assert resp.status_code == 400
    assert "ספטמבר" in resp.json()["error"] or "09" in resp.json()["error"]
    drive_mock.assert_not_called()
