"""שליחת הצעת מחיר בוואטסאפ/מייל כשאין קובץ מקומי.

בפרודקשן (Vercel) הקובץ המקומי חי רק בתוך הבקשה שיצרה אותו, ולכן finalize
מחזיר בכוונה quote_file ריק — והשליחה נפלה עם "חסר קובץ הצעת מחיר לשליחה"
(הצעה 50397, 22.09.2026). התיקון: נפילה לעותק הדרייב — לפי מזהה מפורש,
ואם אין — דרך שורת ההיסטוריה (שם המזהה מסתתר בתוך document_links_json).
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

import app


DRIVE_ID = "1HkF3wn5CKcIiOVyeowxlejR_7yoZABOT"


def _history_row(**overrides):
    row = {
        "history_id": "hist-1",
        "quote_number": "50397",
        "quote_drive_file_id": "",
        "document_links_json": json.dumps(
            [
                {"name": "הצעת מחיר 50397 ב-Drive", "url": f"https://drive.google.com/file/d/{DRIVE_ID}/view?usp=drivesdk"},
                {"name": "תיקיית Drive", "url": "https://drive.google.com/drive/folders/1q2GgN9tKSknNcNOD7DYcy3DyVbrrgkd3"},
            ],
            ensure_ascii=False,
        ),
    }
    row.update(overrides)
    return row


def _fake_download(monkeypatch, calls):
    def fake(file_id, target):
        calls.append(file_id)
        target.write_bytes(b"%PDF-1.4 fake")
        return target

    monkeypatch.setattr(app, "download_drive_file", fake)


# ── מזהה הדרייב משורת היסטוריה ───────────────────────────────────────────────

def test_the_dedicated_column_wins_when_present():
    row = _history_row(quote_drive_file_id="explicit-column-id-000000000")
    assert app._quote_history_row_drive_file_id(row) == "explicit-column-id-000000000"


def test_the_id_is_mined_from_the_document_links():
    """finalize לא כותב את העמודה הייעודית — המזהה קיים רק בקישור /file/d/."""
    assert app._quote_history_row_drive_file_id(_history_row()) == DRIVE_ID


def test_a_folder_link_is_never_mistaken_for_the_file():
    row = _history_row(document_links_json=json.dumps(
        [{"name": "תיקיית Drive", "url": "https://drive.google.com/drive/folders/1q2GgN9tKSknNcNOD7DYcy3DyVbrrgkd3"}]
    ))
    assert app._quote_history_row_drive_file_id(row) == ""


# ── ה-resolver ───────────────────────────────────────────────────────────────

def test_a_living_local_file_is_preferred(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "OUTPUT_DIR", tmp_path)
    local = tmp_path / "orders" / "quote.pdf"
    local.parent.mkdir(parents=True)
    local.write_bytes(b"%PDF-1.4 local")
    calls: list[str] = []
    _fake_download(monkeypatch, calls)

    resolved = app._resolve_quote_pdf_for_send(quote_file="orders/quote.pdf", quote_drive_file_id=DRIVE_ID)
    assert resolved == local
    assert calls == []


def test_an_explicit_drive_id_is_downloaded_with_a_readable_name(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "OUTPUT_DIR", tmp_path)
    calls: list[str] = []
    _fake_download(monkeypatch, calls)

    resolved = app._resolve_quote_pdf_for_send(quote_drive_file_id=DRIVE_ID, quote_number="50397")
    assert calls == [DRIVE_ID]
    assert resolved is not None and resolved.exists()
    assert resolved.name == "הצעת מחיר 50397.pdf"


def test_history_lookup_fills_in_the_missing_drive_id(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(app, "load_quote_history_rows", lambda: [_history_row()])
    calls: list[str] = []
    _fake_download(monkeypatch, calls)

    resolved = app._resolve_quote_pdf_for_send(history_id="hist-1")
    assert calls == [DRIVE_ID]
    assert resolved is not None and resolved.name == "הצעת מחיר 50397.pdf"


def test_nothing_to_resolve_returns_none(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(app, "load_quote_history_rows", lambda: [])
    assert app._resolve_quote_pdf_for_send(quote_file="", history_id="missing") is None


def test_a_failed_download_degrades_to_none(tmp_path, monkeypatch):
    monkeypatch.setattr(app, "OUTPUT_DIR", tmp_path)

    def boom(file_id, target):
        raise RuntimeError("drive down")

    monkeypatch.setattr(app, "download_drive_file", boom)
    assert app._resolve_quote_pdf_for_send(quote_drive_file_id=DRIVE_ID) is None


# ── נקודת הקצה של הוואטסאפ ───────────────────────────────────────────────────

def test_whatsapp_send_succeeds_from_drive_alone(client, tmp_path, monkeypatch):
    """התרחיש של 50397: quote_file ריק, רק מזהה דרייב ביד."""
    monkeypatch.setattr(app, "OUTPUT_DIR", tmp_path)
    calls: list[str] = []
    _fake_download(monkeypatch, calls)
    sender = AsyncMock()
    monkeypatch.setattr(app, "send_files_via_whatsapp", sender)

    response = client.post("/quote-send-whatsapp", json={
        "phone": "0501234567",
        "message": "הצעת מחיר 50397",
        "quote_file": "",
        "quote_drive_file_id": DRIVE_ID,
        "quote_document_number": "50397",
    })
    assert response.status_code == 200
    assert calls == [DRIVE_ID]
    sent_paths = sender.call_args.kwargs["file_paths"]
    assert sent_paths and sent_paths[0].endswith("הצעת מחיר 50397.pdf")


def test_whatsapp_send_still_fails_clearly_when_nothing_exists(client, tmp_path, monkeypatch):
    monkeypatch.setattr(app, "OUTPUT_DIR", tmp_path)
    monkeypatch.setattr(app, "load_quote_history_rows", lambda: [])
    response = client.post("/quote-send-whatsapp", json={
        "phone": "0501234567",
        "message": "הצעה",
        "quote_file": "",
    })
    assert response.status_code == 404
    assert "Drive" in response.json()["error"]
