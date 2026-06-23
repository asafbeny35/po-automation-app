from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "supabase" / "seed" / "current_state"

DOMAIN_FILES: dict[str, str] = {
    "customers": "customers_cache.json",
    "inactive_customers": "inactive_customers_cache.json",
    "order_history": "order_history_cache.json",
    "quote_history": "quote_history_cache.json",
    "working_orders": "working_orders_cache.json",
    "delivery_confirmations": "delivery_confirmations_cache.json",
    "delivery_contacts": "delivery_contacts_cache.json",
    "project_managers": "project_managers_cache.json",
    "marketing_pipeline": "marketing_pipeline_cache.json",
    "marketing_history": "marketing_history_cache.json",
    "marketing_reminders": "marketing_reminders_cache.json",
    "marketing_work_managers": "marketing_work_managers_cache.json",
    "marketing_construction_companies": "marketing_construction_companies_cache.json",
    "finance_invoices": "finance_invoices_cache.json",
    "finance_customer_withholdings": "finance_customer_withholdings_cache.json",
    "finance_bank_movements": "finance_bank_movements_cache.json",
    "payments_transfer": "payments_transfer_cache.json",
    "hr_employees": "hr_employees_cache.json",
    "hr_hours": "hr_hours_cache.json",
    "hr_payroll": "hr_payroll_cache.json",
    "hr_contributions": "hr_contributions_cache.json",
    "hr_documents": "hr_documents_cache.json",
    "hr_payslip_prep_history": "hr_payslip_prep_history_cache.json",
}


def _read_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize_rows(payload):
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
        return payload["rows"]
    return [payload]


def export_seed(output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "domains": {},
    }

    for domain, relative_path in DOMAIN_FILES.items():
        source_path = ROOT / relative_path
        payload = _read_json(source_path)
        rows = _normalize_rows(payload)
        out_path = output_dir / f"{domain}.json"
        out_path.write_text(
            json.dumps(rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest["domains"][domain] = {
            "source_file": relative_path,
            "rows": len(rows),
            "export_file": str(out_path.relative_to(ROOT)),
        }

    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Export current local state into canonical Supabase seed files.")
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Directory for exported JSON seed files.",
    )
    args = parser.parse_args()
    output_dir = Path(args.output_dir).resolve()
    manifest = export_seed(output_dir)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
