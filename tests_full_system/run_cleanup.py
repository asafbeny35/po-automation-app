from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services import google_sheets  # noqa: E402
from services.google_drive_sync import delete_file as delete_drive_item  # noqa: E402
from tests_full_system.settings import SETTINGS  # noqa: E402


MARKERS = (
    SETTINGS.visible_test_tag,
    SETTINGS.visible_test_name_base,
    "TEST-",
    "TEST-SKU",
)


@dataclass
class CleanupReport:
    dry_run: bool
    markers: list[str]
    datasets: list[dict] = field(default_factory=list)
    drive: dict = field(default_factory=lambda: {"files_deleted": [], "folders_deleted": [], "errors": []})
    local: dict = field(default_factory=lambda: {"paths_deleted": [], "errors": []})
    notes: list[str] = field(default_factory=list)

    def add_dataset(self, name: str, total_rows: int, matched_rows: int, applied: bool) -> None:
        self.datasets.append(
            {
                "name": name,
                "total_rows": total_rows,
                "matched_rows": matched_rows,
                "applied": applied,
            }
        )


def _normalized_text(value: object) -> str:
    return str(value or "").strip()


def _row_contains_markers(row: dict) -> bool:
    for value in row.values():
        if isinstance(value, str):
            normalized = value.strip()
            if any(marker in normalized for marker in MARKERS):
                return True
    return False


def _extract_drive_id_from_url(value: str) -> str:
    raw = _normalized_text(value)
    if not raw:
        return ""
    patterns = [
        r"/file/d/([a-zA-Z0-9_-]+)",
        r"/folders/([a-zA-Z0-9_-]+)",
        r"[?&]id=([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, raw)
        if match:
            return match.group(1)
    return ""


def _collect_drive_refs(row: dict) -> tuple[set[str], set[str]]:
    file_ids: set[str] = set()
    folder_ids: set[str] = set()
    for key, value in row.items():
        normalized_key = str(key or "").strip().lower()
        normalized_value = _normalized_text(value)
        if not normalized_value:
            continue
        if "drive_file_id" in normalized_key:
            file_ids.add(normalized_value)
        elif "drive_folder_id" in normalized_key:
            folder_ids.add(normalized_value)
        elif "drive_url" in normalized_key or "folder_url" in normalized_key or "web_view_link" in normalized_key:
            extracted = _extract_drive_id_from_url(normalized_value)
            if extracted:
                if "folder" in normalized_key:
                    folder_ids.add(extracted)
                else:
                    file_ids.add(extracted)
        elif normalized_key == "document_links_json":
            try:
                payload = json.loads(normalized_value)
            except Exception:
                payload = []
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        extracted = _extract_drive_id_from_url(_normalized_text(item.get("url")))
                        if extracted:
                            file_ids.add(extracted)
    return file_ids, folder_ids


def _collect_local_paths(row: dict) -> set[Path]:
    paths: set[Path] = set()
    for key, value in row.items():
        normalized_key = str(key or "").strip().lower()
        normalized_value = _normalized_text(value)
        if "path" not in normalized_key or not normalized_value:
            continue
        candidate = Path(normalized_value)
        if candidate.exists():
            paths.add(candidate)
    return paths


def _delete_drive_ids(ids: Iterable[str], *, dry_run: bool, report_bucket: list[str], errors: list[str]) -> None:
    for item_id in sorted({str(item or "").strip() for item in ids if str(item or "").strip()}):
        if dry_run:
            report_bucket.append(item_id)
            continue
        try:
            delete_drive_item(item_id)
            report_bucket.append(item_id)
        except Exception as exc:
            errors.append(f"{item_id}: {exc}")


def _delete_local_path(path: Path, *, dry_run: bool, report: CleanupReport) -> None:
    target = path.resolve()
    if dry_run:
        report.local["paths_deleted"].append(str(target))
        return
    try:
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=False)
        else:
            target.unlink(missing_ok=True)
        report.local["paths_deleted"].append(str(target))
    except Exception as exc:
        report.local["errors"].append(f"{target}: {exc}")


def _cleanup_dataset(
    *,
    name: str,
    load_rows: Callable[[], list[dict]],
    save_rows: Callable[[list[dict]], object] | None,
    report: CleanupReport,
    drive_file_ids: set[str],
    drive_folder_ids: set[str],
    local_paths: set[Path],
) -> None:
    rows = load_rows()
    matched = [row for row in rows if _row_contains_markers(row)]
    survivors = [row for row in rows if not _row_contains_markers(row)]
    for row in matched:
        row_file_ids, row_folder_ids = _collect_drive_refs(row)
        drive_file_ids.update(row_file_ids)
        drive_folder_ids.update(row_folder_ids)
        local_paths.update(_collect_local_paths(row))
    if matched and save_rows and not report.dry_run:
        save_rows(survivors)
    report.add_dataset(name=name, total_rows=len(rows), matched_rows=len(matched), applied=bool(matched and save_rows and not report.dry_run))


def _cleanup_payments(report: CleanupReport) -> None:
    state = google_sheets.load_payment_transfer_rows(force_refresh=True)
    rows = list(state.get("all_rows") or [])
    matched = [row for row in rows if _row_contains_markers(row)]
    deleted = 0
    for row in matched:
        if report.dry_run:
            deleted += 1
            continue
        try:
            google_sheets.delete_payment_transfer_row(
                sheet_title=str(row.get("_sheet_title") or "").strip(),
                row_number=int(row.get("_sheet_row") or 0),
                row=row,
            )
            deleted += 1
        except Exception as exc:
            report.local["errors"].append(f"payments::{row.get('_sheet_title')}::{row.get('_sheet_row')}: {exc}")
    report.add_dataset(name="payments_transfer", total_rows=len(rows), matched_rows=len(matched), applied=bool(deleted and not report.dry_run))


def _cleanup_suppressions(report: CleanupReport) -> None:
    suppression_file = getattr(google_sheets, "_DELIVERY_CONFIRMATION_SUPPRESSIONS_FILE", None)
    if not suppression_file:
        return
    target = Path(suppression_file)
    if not target.exists():
        return
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        report.notes.append(f"Could not parse suppressions file: {exc}")
        return
    if not isinstance(payload, list):
        return
    matched = [item for item in payload if any(marker in str(item or "") for marker in MARKERS)]
    survivors = [item for item in payload if not any(marker in str(item or "") for marker in MARKERS)]
    if matched and not report.dry_run:
        target.write_text(json.dumps(survivors, ensure_ascii=False, indent=2), encoding="utf-8")
    report.add_dataset(
        name="delivery_confirmation_suppressions",
        total_rows=len(payload),
        matched_rows=len(matched),
        applied=bool(matched and not report.dry_run),
    )


def _cleanup_local_artifacts(report: CleanupReport) -> None:
    known_dirs = [
        SETTINGS.artifacts_dir,
        PROJECT_ROOT / "output",
        PROJECT_ROOT / "uploads",
    ]
    for root in known_dirs:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*"), reverse=True):
            raw = str(path)
            if any(marker in raw for marker in MARKERS):
                _delete_local_path(path, dry_run=report.dry_run, report=report)


def run_cleanup(*, apply: bool, include_drive: bool, include_local: bool, include_sheets: bool) -> CleanupReport:
    report = CleanupReport(dry_run=not apply, markers=list(MARKERS))
    drive_file_ids: set[str] = set()
    drive_folder_ids: set[str] = set()
    local_paths: set[Path] = set()

    if include_sheets:
        dataset_specs = [
            ("customers_active", lambda: google_sheets.load_customer_rows("active"), lambda rows: google_sheets.save_customer_rows(rows, "active")),
            ("customers_inactive", google_sheets.load_inactive_customer_rows, google_sheets.save_inactive_customer_rows),
            ("order_history", lambda: google_sheets.load_order_history_rows(force_refresh=True), google_sheets.save_order_history_rows),
            ("quote_history", lambda: google_sheets.load_quote_history_rows(force_refresh=True), google_sheets.save_quote_history_rows),
            ("delivery_confirmations", google_sheets.load_delivery_confirmation_rows, google_sheets.save_delivery_confirmation_rows),
            ("delivery_contacts", google_sheets.load_delivery_contact_rows, google_sheets.save_delivery_contact_rows),
            ("inventory_raw", lambda: google_sheets.load_inventory_rows("raw"), lambda rows: google_sheets.save_inventory_rows("raw", rows)),
            ("inventory_finish", lambda: google_sheets.load_inventory_rows("finish"), lambda rows: google_sheets.save_inventory_rows("finish", rows)),
            ("inventory_contacts", lambda: google_sheets.load_inventory_rows("contacts"), lambda rows: google_sheets.save_inventory_rows("contacts", rows)),
            ("supplier_delivery_notes", lambda: google_sheets.load_supplier_delivery_note_rows(force_refresh=True), google_sheets.save_supplier_delivery_note_rows),
            ("inventory_purchase_orders", lambda: google_sheets.load_inventory_purchase_order_rows(force_refresh=True), google_sheets.save_inventory_purchase_order_rows),
            ("pricing_items", lambda: google_sheets.load_pricing_rows("items", force_refresh=True), lambda rows: google_sheets.save_pricing_rows("items", rows)),
            ("pricing_components", lambda: google_sheets.load_pricing_rows("components", force_refresh=True), lambda rows: google_sheets.save_pricing_rows("components", rows)),
            ("marketing_notes", lambda: google_sheets.load_marketing_rows("notes", force_refresh=True), lambda rows: google_sheets.save_marketing_rows("notes", rows)),
            ("marketing_reminders", lambda: google_sheets.load_marketing_rows("reminders", force_refresh=True), lambda rows: google_sheets.save_marketing_rows("reminders", rows)),
            ("marketing_history", lambda: google_sheets.load_marketing_rows("history", force_refresh=True), lambda rows: google_sheets.save_marketing_rows("history", rows)),
            ("marketing_pipeline", lambda: google_sheets.load_marketing_rows("pipeline", force_refresh=True), lambda rows: google_sheets.save_marketing_rows("pipeline", rows)),
            ("marketing_work_managers", lambda: google_sheets.load_marketing_rows("work_managers", force_refresh=True), lambda rows: google_sheets.save_marketing_rows("work_managers", rows)),
            ("marketing_construction_companies", lambda: google_sheets.load_marketing_rows("construction_companies", force_refresh=True), lambda rows: google_sheets.save_marketing_rows("construction_companies", rows)),
            ("finance_invoices", lambda: google_sheets.load_marketing_rows("finance_invoices", force_refresh=True), lambda rows: google_sheets.save_marketing_rows("finance_invoices", rows)),
            ("finance_settings", lambda: google_sheets.load_marketing_rows("finance_settings", force_refresh=True), lambda rows: google_sheets.save_marketing_rows("finance_settings", rows)),
        ]
        for name, load_rows, save_rows in dataset_specs:
            _cleanup_dataset(
                name=name,
                load_rows=load_rows,
                save_rows=save_rows,
                report=report,
                drive_file_ids=drive_file_ids,
                drive_folder_ids=drive_folder_ids,
                local_paths=local_paths,
            )
        _cleanup_payments(report)
        _cleanup_suppressions(report)

    if include_drive:
        _delete_drive_ids(drive_file_ids, dry_run=report.dry_run, report_bucket=report.drive["files_deleted"], errors=report.drive["errors"])
        _delete_drive_ids(drive_folder_ids, dry_run=report.dry_run, report_bucket=report.drive["folders_deleted"], errors=report.drive["errors"])

    if include_local:
        for path in sorted(local_paths, reverse=True):
            _delete_local_path(path, dry_run=report.dry_run, report=report)
        _cleanup_local_artifacts(report)

    report.notes.append("WhatsApp and sent emails are not auto-recalled by this cleanup script.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Cleanup TEST / נעלולי פלא artifacts created by the full-system test suite.")
    parser.add_argument("--apply", action="store_true", help="Actually delete / rewrite data. Default is dry-run only.")
    parser.add_argument("--no-drive", action="store_true", help="Skip Google Drive cleanup.")
    parser.add_argument("--no-local", action="store_true", help="Skip local artifact cleanup.")
    parser.add_argument("--no-sheets", action="store_true", help="Skip Google Sheets cleanup.")
    parser.add_argument("--report-json", default="", help="Optional path to write the cleanup report as JSON.")
    args = parser.parse_args()

    report = run_cleanup(
        apply=args.apply,
        include_drive=not args.no_drive,
        include_local=not args.no_local,
        include_sheets=not args.no_sheets,
    )

    rendered = json.dumps(
        {
            "dry_run": report.dry_run,
            "markers": report.markers,
            "datasets": report.datasets,
            "drive": report.drive,
            "local": report.local,
            "notes": report.notes,
        },
        ensure_ascii=False,
        indent=2,
    )
    print(rendered)
    if args.report_json:
        Path(args.report_json).write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
