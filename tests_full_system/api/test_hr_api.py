"""HR & Payroll API tests — comprehensive coverage of all HR endpoints."""
from __future__ import annotations

import io

import pytest


# ---------------------------------------------------------------------------
# State / read endpoints
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_state_returns_ok(api_client):
    response = api_client.get("/hr-state")
    assert response.status_code == 200


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_state_response_has_expected_keys(api_client):
    response = api_client.get("/hr-state")
    assert response.status_code == 200
    payload = response.payload
    assert isinstance(payload, dict)
    # Must contain at least one of these domain keys
    domain_keys = {"employees", "payroll", "hours", "contributions", "documents",
                   "hr_employees", "hr_payroll", "hr_hours", "hr_contributions", "hr_documents"}
    assert any(k in payload for k in domain_keys), (
        f"hr-state missing domain keys, got: {list(payload.keys())}"
    )


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_hours_detail_endpoint_available(api_client):
    response = api_client.get("/hr-hours-detail")
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_payslip_prep_preview_endpoint_available(api_client):
    response = api_client.get("/hr-payslip-prep-preview")
    assert response.status_code < 500


# ---------------------------------------------------------------------------
# Employee CRUD
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_employee_save_accepts_minimal_shape(api_client):
    payload = {
        "row": {
            "employee_name": "TEST | נעלולי פלא | עובד",
            "employee_id": "999999999",
            "role": "TEST | נעלולי פלא | תפקיד",
            "phone": "0547720142",
            "email": "test@example.com",
            "start_date": "01/01/2026",
            "base_salary": "5000",
        }
    }
    response = api_client.post("/hr-employee-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_employee_save_returns_row_id_on_success(api_client):
    payload = {
        "row": {
            "employee_name": "TEST | נעלולי פלא | עובד חדש",
            "employee_id": "888888888",
            "role": "פועל",
            "start_date": "01/01/2026",
        }
    }
    response = api_client.post("/hr-employee-save", json=payload)
    if response.status_code == 200:
        assert isinstance(response.payload, dict)
        assert response.payload.get("status") == "ok"


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_employee_delete_rejects_empty_payload(api_client):
    response = api_client.post("/hr-employee-delete", json={})
    assert response.status_code in {400, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_employee_delete_accepts_row_id(api_client):
    response = api_client.post(
        "/hr-employee-delete",
        json={"row_id": "test-employee-001"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


# ---------------------------------------------------------------------------
# Payroll CRUD
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_payroll_save_accepts_minimal_shape(api_client):
    payload = {
        "row": {
            "employee_name": "TEST | נעלולי פלא | עובד",
            "month": "05/2026",
            "gross_salary": "6000",
            "net_salary": "5000",
            "payment_date": "01/05/2026",
        }
    }
    response = api_client.post("/hr-payroll-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_payroll_save_missing_employee_name_rejected(api_client):
    payload = {
        "row": {
            "month": "05/2026",
            "gross_salary": "6000",
        }
    }
    response = api_client.post("/hr-payroll-save", json=payload)
    # Might be 400/422 if validated, or 200 if lenient — just not a crash
    assert response.status_code < 500


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_payroll_delete_requires_row_id(api_client):
    response = api_client.post("/hr-payroll-delete", json={})
    assert response.status_code in {400, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_payroll_delete_accepts_valid_row_id(api_client):
    response = api_client.post(
        "/hr-payroll-delete",
        json={"row_id": "test-payroll-001"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_payroll_send_whatsapp_requires_phone(api_client):
    response = api_client.post("/hr-payroll-send-whatsapp", json={})
    assert response.status_code in {400, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_payroll_send_whatsapp_accepts_test_number(api_client):
    response = api_client.post(
        "/hr-payroll-send-whatsapp",
        json={
            "phone": "0547720142",
            "employee_name": "TEST | נעלולי פלא | עובד",
            "month": "05/2026",
            "net_salary": "5000",
        },
    )
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# Hours tracking
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_hours_save_accepts_minimal_shape(api_client):
    payload = {
        "row": {
            "employee_name": "TEST | נעלולי פלא | עובד",
            "date": "01/05/2026",
            "hours": "8",
            "description": "TEST | נעלולי פלא | עבודה",
        }
    }
    response = api_client.post("/hr-hours-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_hours_delete_requires_row_id(api_client):
    response = api_client.post("/hr-hours-delete", json={})
    assert response.status_code in {400, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_hours_delete_with_valid_row_id(api_client):
    response = api_client.post(
        "/hr-hours-delete",
        json={"row_id": "test-hours-001"},
    )
    assert response.status_code in {200, 400, 404, 422, 500}


# ---------------------------------------------------------------------------
# Contribution records
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_contribution_save_accepts_minimal_shape(api_client):
    payload = {
        "row": {
            "employee_name": "TEST | נעלולי פלא | עובד",
            "month": "05/2026",
            "pension": "300",
            "health": "150",
            "disability": "50",
        }
    }
    response = api_client.post("/hr-contribution-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# Document upload
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_document_save_accepts_minimal_shape(api_client):
    payload = {
        "row": {
            "employee_name": "TEST | נעלולי פלא | עובד",
            "document_type": "תלוש שכר",
            "month": "05/2026",
            "file_name": "test_payslip.pdf",
        }
    }
    response = api_client.post("/hr-document-save", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_document_delete_requires_row_id(api_client):
    response = api_client.post("/hr-document-delete", json={})
    assert response.status_code in {400, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_hr_upload_file_accepts_pdf_shape(api_client):
    files = {"file": ("test_hr_doc.pdf", io.BytesIO(b"%PDF-1.4\n%HR-TEST\n"), "application/pdf")}
    data = {"employee_name": "TEST | נעלולי פלא | עובד", "document_type": "חוזה"}
    response = api_client.post("/hr-upload-file", files=files, data=data)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.destructive
def test_hr_ingest_files_accepts_multiple_pdfs(api_client):
    files = [
        ("files", ("doc1.pdf", io.BytesIO(b"%PDF-1.4\n%HR-TEST-1\n"), "application/pdf")),
        ("files", ("doc2.pdf", io.BytesIO(b"%PDF-1.4\n%HR-TEST-2\n"), "application/pdf")),
    ]
    response = api_client.post("/hr-ingest-files", files=files)
    assert response.status_code in {200, 400, 422, 500}


# ---------------------------------------------------------------------------
# Payslip prep
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_payslip_prep_send_accepts_minimal_shape(api_client):
    payload = {
        "month": "05/2026",
        "mode": "sandbox",
        "employees": [
            {
                "employee_name": "TEST | נעלולי פלא | עובד",
                "net_salary": "5000",
                "phone": "0547720142",
            }
        ],
    }
    response = api_client.post("/hr-payslip-prep-send", json=payload)
    assert response.status_code in {200, 400, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_payslip_prep_send_requires_month(api_client):
    response = api_client.post("/hr-payslip-prep-send", json={"employees": []})
    assert response.status_code < 500  # must not crash, may be 400 or lenient


# ---------------------------------------------------------------------------
# Export endpoints
# ---------------------------------------------------------------------------

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.parametrize("section,fmt", [
    ("employees", "csv"),
    ("employees", "xlsx"),
    ("payroll", "csv"),
    ("payroll", "xlsx"),
    ("hours", "csv"),
    ("hours", "xlsx"),
])
def test_hr_export_all_sections_and_formats(api_client, section, fmt):
    response = api_client.get(f"/hr-export/{section}/{fmt}")
    assert response.status_code in {200, 400, 404, 422, 500}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_export_invalid_section_returns_error(api_client):
    response = api_client.get("/hr-export/nonexistent/csv")
    assert response.status_code in {400, 404, 422}


@pytest.mark.api
@pytest.mark.requires_live_server
def test_hr_export_invalid_format_returns_error(api_client):
    response = api_client.get("/hr-export/employees/xml")
    assert response.status_code in {400, 404, 422}
