"""ייבוא הצעות מחיר שהופקו ישירות במורנינג לתוך היסטוריית ההצעות.

בלחיצה על "טען היסטוריה" ממזגים את ההצעות שלנו (מהשיט) עם הצעות שהונפקו
ישירות במורנינג (לא דרך המערכת), בלי כפילויות לפי מספר ההצעה, ובלי לגעת
בשיט שלנו — הן נשמרות במטמון נפרד לתצוגה בלבד.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

import app


def _doc(number, doc_id, name, amount, date="2026-09-22"):
    return {
        "id": doc_id,
        "number": number,
        "date": date,
        "customer_name": name,
        "customer_id": "512947185",
        "item_name": "פריט לדוגמה",
        "source_url": f"https://api.greeninvoice.co.il/api/v1/documents/download?d={doc_id}",
        "raw": {"amount": amount},
    }


class _FakeClient:
    def __init__(self, docs):
        self._docs = docs

    async def get_quote_documents(self, date_from, date_to, page_size=100, max_pages=48):
        return list(self._docs)

    def _extract_number(self, item, keys):
        for key in keys:
            if item.get(key):
                return float(item[key])
        return 0.0


def _patch_client(docs):
    fake = _FakeClient(docs)
    return (
        patch("app.get_mode_config", return_value={"base_url": "x", "api_key": "y", "api_secret": "z"}),
        patch("app.GreenInvoiceClient", return_value=fake),
    )


@pytest.fixture(autouse=True)
def _clean_cache():
    app._MORNING_QUOTE_HISTORY_CACHE = []
    yield
    app._MORNING_QUOTE_HISTORY_CACHE = []


# ── מיפוי וסינון ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_morning_quotes_are_mapped_to_history_rows():
    docs = [_doc("50399", "id-a", 'רם אדרת', 15458.0)]
    cm1, cm2 = _patch_client(docs)
    with cm1, cm2:
        rows = await app._fetch_morning_quote_history_rows(existing_quote_numbers=set())
    assert len(rows) == 1
    row = rows[0]
    assert row["quote_number"] == "50399"
    assert row["morning_source"] is True
    assert row["input_source"] == "מורנינג"
    assert row["quote_date"] == "22/09/2026"
    assert row["customer_name"] == "רם אדרת"
    assert row["total"] == "15458.00"
    assert "greeninvoice" in row["document_links_json"]


@pytest.mark.asyncio
async def test_quotes_we_already_have_are_skipped():
    docs = [_doc("50399", "id-a", "A", 100.0), _doc("50400", "id-b", "B", 200.0)]
    cm1, cm2 = _patch_client(docs)
    with cm1, cm2:
        rows = await app._fetch_morning_quote_history_rows(existing_quote_numbers={"50399"})
    numbers = [r["quote_number"] for r in rows]
    assert numbers == ["50400"]


@pytest.mark.asyncio
async def test_vat_is_split_out_of_the_gross_amount():
    docs = [_doc("50400", "id-b", "B", 1180.0)]
    cm1, cm2 = _patch_client(docs)
    with cm1, cm2:
        rows = await app._fetch_morning_quote_history_rows(existing_quote_numbers=set())
    assert rows[0]["subtotal"] == "1000.00"
    assert rows[0]["vat"] == "180.00"
    assert rows[0]["total"] == "1180.00"


# ── מיזוג ─────────────────────────────────────────────────────────────────────

def test_combined_rows_dedupe_morning_against_our_own():
    app._MORNING_QUOTE_HISTORY_CACHE = [
        {"quote_number": "50399", "morning_source": True},
        {"quote_number": "50400", "morning_source": True},
    ]
    combined = app._combined_quote_history_rows([{"quote_number": "50399"}])
    morning_numbers = [r["quote_number"] for r in combined if r.get("morning_source")]
    assert morning_numbers == ["50400"]


# ── נקודת הקצה ────────────────────────────────────────────────────────────────

def test_refresh_merges_morning_rows_into_payload(client):
    docs = [_doc("50401", "id-c", "כפיים בנייה", 1328.68)]
    cm1, cm2 = _patch_client(docs)
    with cm1, cm2, patch("app.load_quote_history_rows", return_value=[]):
        resp = client.post("/quote-history-refresh")
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    morning = [r for r in rows if r.get("morning_source")]
    assert len(morning) == 1
    assert morning[0]["quote_number"] == "50401"
    assert morning[0]["input_source"] == "מורנינג"


def test_refresh_survives_a_morning_import_failure(client):
    our_rows = [{"quote_number": "50000", "history_id": "h1", "customer_name": "לקוח"}]
    with (
        patch("app.load_quote_history_rows", return_value=our_rows),
        patch("app._fetch_morning_quote_history_rows", side_effect=Exception("morning down")),
    ):
        resp = client.post("/quote-history-refresh")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "מורנינג" in data.get("warning", "")
    # ההצעה שלנו עדיין מוצגת למרות כשל הייבוא
    assert any(r["quote_number"] == "50000" for r in data["rows"])


def test_resolve_opens_a_morning_quote_from_cache(client):
    app._MORNING_QUOTE_HISTORY_CACHE = [
        {
            "history_id": "morning::id-c",
            "quote_number": "50401",
            "morning_source": True,
            "document_links_json": '[{"name": "הצעת מחיר במורנינג", "url": "https://api.greeninvoice.co.il/api/v1/documents/download?d=abc"}]',
        }
    ]
    with (
        patch("app.load_quote_history_rows", return_value=[]),
        patch("app.get_cached_quote_history_rows", return_value=[]),
    ):
        resp = client.get("/quote-history-quote-resolve", params={"history_id": "morning::id-c"})
    assert resp.status_code == 200
    assert resp.json()["url"].startswith("https://api.greeninvoice.co.il")
