from __future__ import annotations

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEED_DIR = ROOT / "supabase" / "seed" / "current_state"
OUT_DIR = ROOT / "supabase" / "import_sql"


DOMAIN_CONFIG: dict[str, dict] = {
    "customers": {
        "table": "customers",
        "chunk_size": 25,
        "json_column": "payload",
        "column_map": {
            "id": "coalesce(nullif(payload->>'customer_guid',''), nullif(payload->>'customer_id',''), payload->>'customer_name')",
            "customer_guid": "payload->>'customer_guid'",
            "customer_name": "payload->>'customer_name'",
            "customer_id": "payload->>'customer_id'",
            "source_mode": "payload->>'source_mode'",
            "active": "(payload->>'active')::boolean",
            "send": "case when payload ? 'send' then (payload->>'send')::boolean else null end",
            "department": "payload->>'department'",
            "accounting_key": "payload->>'accounting_key'",
            "payment_terms_days": "case when payload->>'payment_terms_days' = '' then null else (payload->>'payment_terms_days')::integer end",
            "phone": "payload->>'phone'",
            "mobile": "payload->>'mobile'",
            "emails": "coalesce(payload->'emails','[]'::jsonb)",
            "contact_person": "payload->>'contact_person'",
            "address": "payload->>'address'",
            "city": "payload->>'city'",
            "zip": "payload->>'zip'",
            "country": "payload->>'country'",
            "bank_name": "payload->>'bank_name'",
            "bank_branch": "payload->>'bank_branch'",
            "bank_account": "payload->>'bank_account'",
            "remarks": "payload->>'remarks'",
            "income_amount": "case when payload->>'income_amount' = '' then null else (payload->>'income_amount')::numeric end",
            "payment_amount": "case when payload->>'payment_amount' = '' then null else (payload->>'payment_amount')::numeric end",
            "balance_amount": "case when payload->>'balance_amount' = '' then null else (payload->>'balance_amount')::numeric end",
            "creation_date": "payload->>'creation_date'",
            "last_update_date": "payload->>'last_update_date'",
            "customer_domain": "payload->>'customer_domain'",
            "bank_details_updated_sent": "case when payload ? 'bank_details_updated_sent' then (payload->>'bank_details_updated_sent')::boolean else null end",
            "synced_at": "case when payload->>'synced_at' = '' then null else (payload->>'synced_at')::timestamptz end",
            "raw_payload": "payload",
        },
    },
    "inactive_customers": {
        "table": "customers",
        "chunk_size": 25,
        "json_column": "payload",
        "column_map": {
            "id": "coalesce(nullif(payload->>'customer_guid',''), nullif(payload->>'customer_id',''), payload->>'customer_name')",
            "customer_guid": "payload->>'customer_guid'",
            "customer_name": "payload->>'customer_name'",
            "customer_id": "payload->>'customer_id'",
            "source_mode": "payload->>'source_mode'",
            "active": "false",
            "send": "case when payload ? 'send' then (payload->>'send')::boolean else null end",
            "department": "payload->>'department'",
            "accounting_key": "payload->>'accounting_key'",
            "payment_terms_days": "case when payload->>'payment_terms_days' = '' then null else (payload->>'payment_terms_days')::integer end",
            "phone": "payload->>'phone'",
            "mobile": "payload->>'mobile'",
            "emails": "coalesce(payload->'emails','[]'::jsonb)",
            "contact_person": "payload->>'contact_person'",
            "address": "payload->>'address'",
            "city": "payload->>'city'",
            "zip": "payload->>'zip'",
            "country": "payload->>'country'",
            "bank_name": "payload->>'bank_name'",
            "bank_branch": "payload->>'bank_branch'",
            "bank_account": "payload->>'bank_account'",
            "remarks": "payload->>'remarks'",
            "income_amount": "case when payload->>'income_amount' = '' then null else (payload->>'income_amount')::numeric end",
            "payment_amount": "case when payload->>'payment_amount' = '' then null else (payload->>'payment_amount')::numeric end",
            "balance_amount": "case when payload->>'balance_amount' = '' then null else (payload->>'balance_amount')::numeric end",
            "creation_date": "payload->>'creation_date'",
            "last_update_date": "payload->>'last_update_date'",
            "customer_domain": "payload->>'customer_domain'",
            "bank_details_updated_sent": "case when payload ? 'bank_details_updated_sent' then (payload->>'bank_details_updated_sent')::boolean else null end",
            "synced_at": "case when payload->>'synced_at' = '' then null else (payload->>'synced_at')::timestamptz end",
            "raw_payload": "payload",
        },
    },
}


def _json_literal(rows: list[dict]) -> str:
    return json.dumps(rows, ensure_ascii=False).replace("$json$", "$json $$")


def _build_upsert_sql(table: str, json_column: str, column_map: dict[str, str], rows: list[dict]) -> str:
    columns = list(column_map.keys())
    select_exprs = [f"{expr} as {col}" for col, expr in column_map.items()]
    updates = [f"{col} = excluded.{col}" for col in columns if col not in {"id", "created_at"}]
    json_payload = _json_literal(rows)
    return f"""with source as (
  select value as {json_column}
  from jsonb_array_elements($json${json_payload}$json$::jsonb)
)
insert into public.{table} (
  {", ".join(columns)}
)
select
  {", ".join(select_exprs)}
from source
on conflict (id) do update
set {", ".join(updates)};"""


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, list[str]] = {}
    for domain, config in DOMAIN_CONFIG.items():
        seed_path = SEED_DIR / f"{domain}.json"
        if not seed_path.exists():
            continue
        rows = json.loads(seed_path.read_text(encoding="utf-8"))
        chunk_size = int(config["chunk_size"])
        files: list[str] = []
        for index in range(math.ceil(len(rows) / chunk_size) or 1):
            chunk = rows[index * chunk_size:(index + 1) * chunk_size]
            if not chunk:
                continue
            sql = _build_upsert_sql(
                table=config["table"],
                json_column=config["json_column"],
                column_map=config["column_map"],
                rows=chunk,
            )
            file_name = f"{domain}_{index + 1:03d}.sql"
            target = OUT_DIR / file_name
            target.write_text(sql, encoding="utf-8")
            files.append(file_name)
        manifest[domain] = files
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
