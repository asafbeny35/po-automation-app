from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.google_sheets import (
    _merge_project_manager_rows,
    _save_project_managers_disk_cache,
    save_project_manager_rows,
)
from services.project_managers import rebuild_project_manager_entries_from_folder


SOURCE_ROOT = Path("/Users/asafbeny/Library/Mobile Documents/com~apple~CloudDocs/Downloads/בן יעקב/מדבקות")
OUTPUT_JSON = PROJECT_ROOT / "project_managers_rebuild_rows.json"


def main():
    rows = rebuild_project_manager_entries_from_folder(SOURCE_ROOT)
    merged_rows = _merge_project_manager_rows(rows)
    OUTPUT_JSON.write_text(json.dumps(merged_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    _save_project_managers_disk_cache(merged_rows)
    print(f"rebuilt_rows={len(rows)}")
    print(f"merged_rows={len(merged_rows)}")
    try:
        result = save_project_manager_rows(merged_rows)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({"saved_to_cache_only": True, "error": str(exc)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
