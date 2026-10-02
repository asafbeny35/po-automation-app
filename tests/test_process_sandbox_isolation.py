"""/process in sandbox mode must not write project managers or upload to the real Drive."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app as app_module


def _run_process(mode):
    pm_sync = AsyncMock()
    drive_sync = MagicMock(return_value={"status": "ok", "source_drive_file_id": "real-id"})
    parse = MagicMock(return_value=SimpleNamespace(customer_name="x", po_number="1", po_date=""))
    captured = {}

    def build(po, mode_arg, filename, file_path, source_drive_file_id):
        captured["source_drive_file_id"] = source_drive_file_id
        return {"status": "ok"}

    async def go():
        with patch.object(app_module, "_store_uploaded_pdf", AsyncMock(return_value=(Path("/tmp/x.pdf"), None))), \
             patch.object(app_module, "parse_purchase_order", parse), \
             patch.object(app_module, "_enrich_po_for_process", AsyncMock(side_effect=lambda po, cfg: po)), \
             patch.object(app_module, "_sync_project_managers_from_pdf_background", pm_sync), \
             patch.object(app_module, "_try_sync_source_po_to_drive_for_process", drive_sync), \
             patch.object(app_module, "_build_process_payload_from_po", build):
            response = await app_module.process(file=SimpleNamespace(filename="po.pdf"), mode=mode)
            await asyncio.sleep(0)
            return response

    response = asyncio.run(go())
    return response, pm_sync, drive_sync, captured


def test_sandbox_skips_project_manager_sync_and_drive_upload():
    response, pm_sync, drive_sync, captured = _run_process("sandbox")
    assert response.status_code == 200
    pm_sync.assert_not_called()
    drive_sync.assert_not_called()
    assert json.loads(response.body)["source_drive_sync_status"] == "skipped_sandbox"
    assert captured["source_drive_file_id"] == ""


@pytest.mark.parametrize("mode", ["prod", "", "SANDBOX", "sandbox_with_transport", "unknown"])
def test_production_and_unknown_modes_keep_previous_behavior(mode):
    response, pm_sync, drive_sync, captured = _run_process(mode)
    pm_sync.assert_called_once()
    drive_sync.assert_called_once()
    assert json.loads(response.body)["source_drive_sync_status"] == "ok"
    assert captured["source_drive_file_id"] == "real-id"
