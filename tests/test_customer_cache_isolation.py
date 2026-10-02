"""Sandbox customer creation adds one SB row and never replaces or deletes stored customers."""
from __future__ import annotations

from unittest.mock import patch

import pytest

import app as app_module
from services import google_sheets, supabase_store

SANDBOX_FETCH = [
    {"customer_guid": "sb-1", "customer_name": "בדיקה", "customer_id": "012345678", "source_mode": "SB"},
    {"customer_guid": "sb-2", "customer_name": "אחר בסנדבוקס", "customer_id": "333333333", "source_mode": "SB"},
]


@pytest.mark.parametrize("mode", ["sandbox", "SANDBOX", " sandbox "])
def test_sandbox_inserts_only_created_row_tagged_sb_and_never_saves_table(mode):
    with patch.object(app_module, "save_customer_rows") as save, \
         patch.object(app_module, "add_customer_row_if_absent", return_value={"inserted": True}) as add:
        app_module._persist_customer_cache_after_create(mode, SANDBOX_FETCH, "בדיקה", "012345678")
    save.assert_not_called()
    add.assert_called_once()
    row = add.call_args.args[0]
    assert row["customer_guid"] == "sb-1" and row["source_mode"] == "SB"


def test_sandbox_forces_sb_tag_and_requires_guid():
    with patch.object(app_module, "add_customer_row_if_absent") as add:
        app_module._persist_customer_cache_after_create("sandbox", [{"customer_guid": "g", "customer_name": "x", "customer_id": "9"}], "x", "9")
        assert add.call_args.args[0]["source_mode"] == "SB"
        add.reset_mock()
        result = app_module._persist_customer_cache_after_create("sandbox", [{"customer_name": "x", "customer_id": "9"}], "x", "9")
    add.assert_not_called()
    assert result["skipped"] is True


def test_sandbox_skips_when_created_customer_not_found():
    with patch.object(app_module, "add_customer_row_if_absent") as add, patch.object(app_module, "save_customer_rows") as save:
        result = app_module._persist_customer_cache_after_create("sandbox", SANDBOX_FETCH, "לא קיים", "555")
    add.assert_not_called(); save.assert_not_called()
    assert result["skipped"] is True


@pytest.mark.parametrize("mode", ["production", "prod"])
def test_production_keeps_existing_save_behavior(mode):
    fetched = [{"customer_guid": "p2", "customer_name": "ב", "customer_id": "2", "source_mode": "PROD"},
               {"customer_guid": "p1", "customer_name": "א", "customer_id": "1", "source_mode": "PROD"}]
    saved = {}
    with patch.object(app_module, "save_customer_rows", side_effect=lambda r, *a, **k: saved.update(rows=r) or {}), \
         patch.object(app_module, "add_customer_row_if_absent") as add:
        app_module._persist_customer_cache_after_create(mode, fetched, "", "")
    assert saved["rows"] == app_module._sort_customer_rows(fetched)
    add.assert_not_called()


def test_row_insert_is_ignore_duplicates_post_only_no_delete():
    calls = []
    with patch.object(supabase_store, "_request_json", side_effect=lambda *a, **k: calls.append((a, k)) or None):
        out = supabase_store.insert_domain_row_if_absent("customers", {"customer_guid": "sb-1", "customer_name": "בדיקה", "customer_id": "012345678", "source_mode": "SB"})
    assert out["inserted"] is True and len(calls) == 1
    (method, path), kwargs = calls[0]
    assert method == "POST" and "customers" in path
    assert kwargs["headers"]["Prefer"].startswith("resolution=ignore-duplicates")
    assert kwargs["payload"][0]["source_mode"] == "SB" and kwargs["payload"][0]["id"] == "sb-1"


def test_row_insert_without_row_level_backend_writes_nothing():
    with patch.object(google_sheets, "_supabase_enabled_for", return_value=False), \
         patch.object(supabase_store, "insert_domain_row_if_absent") as ins:
        result = google_sheets.add_customer_row_if_absent({"customer_guid": "g", "customer_name": "x"})
    ins.assert_not_called()
    assert result["skipped"] is True


def test_finalize_mode_values_map_correctly():
    assert app_module._normalize_customer_mode(app_module.get_mode_config("sandbox")["mode"]) == "sandbox"
    assert app_module._normalize_customer_mode(app_module.get_mode_config("production")["mode"]) == "prod"
