from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED_MANIFEST = ROOT / "supabase" / "seed" / "current_state" / "manifest.json"
OUTPUT_FILE = ROOT / "ios" / "BenYacovMobile" / "App" / "Resources" / "bootstrap_snapshot.json"


def main() -> int:
    manifest = json.loads(SEED_MANIFEST.read_text(encoding="utf-8"))
    domains = manifest.get("domains", {})
    snapshot = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": [
            {"id": "orders", "title": "הזמנות", "count": domains.get("order_history", {}).get("rows", 0)},
            {"id": "quotes", "title": "הצעות מחיר", "count": domains.get("quote_history", {}).get("rows", 0)},
            {"id": "working_orders", "title": "הזמנות בעבודה", "count": domains.get("working_orders", {}).get("rows", 0)},
            {"id": "customers", "title": "לקוחות", "count": domains.get("customers", {}).get("rows", 0)},
            {"id": "finance", "title": "חשבוניות ספק", "count": domains.get("finance_invoices", {}).get("rows", 0)},
            {"id": "payments", "title": "העברות ותשלומים", "count": domains.get("payments_transfer", {}).get("rows", 0)},
            {"id": "marketing", "title": "שיווק", "count": domains.get("marketing_pipeline", {}).get("rows", 0)},
            {"id": "hr", "title": "עובדים ושכר", "count": domains.get("hr_employees", {}).get("rows", 0)},
            {"id": "project_managers", "title": "מנהלי פרויקטים", "count": domains.get("project_managers", {}).get("rows", 0)},
        ],
    }
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(OUTPUT_FILE))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
