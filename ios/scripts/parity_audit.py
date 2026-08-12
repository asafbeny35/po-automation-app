#!/usr/bin/env python3
"""ביקורת פאריטי: כל ראוט בשרת חייב להיות או בשימוש באפליקציה, או מוחרג בנימוק.

מצליב את ROUTE_MANIFEST של השרת מול הנתיבים שקוד הסוויפט קורא בפועל.
ראוט שאינו בשימוש ואינו מוחרג = פער פיצ'ר לא מטופל → יציאה עם שגיאה.
כך פיצ'ר חסר שובר את הבנייה במקום להתגלות על ידי המשתמש.

הרצה: python3 scripts/parity_audit.py [--report]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

IOS_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = IOS_ROOT.parent
APP_SOURCES = IOS_ROOT / "BenYacovManage"
EXCLUSIONS_FILE = IOS_ROOT / "scripts" / "parity_exclusions.json"


def load_server_routes() -> list[dict]:
    manifest_path = PROJECT_ROOT / "tests_full_system" / "manifests" / "routes.py"
    namespace: dict = {"True": True, "False": False}
    exec(manifest_path.read_text(), namespace)  # noqa: S102 — קובץ פנימי של הפרויקט
    return namespace["ROUTE_MANIFEST"]


def collect_app_endpoints() -> set[str]:
    """כל הנתיבים שהאפליקציה קוראת דרך APIClient — כולל נתיבים שמאוחסנים במשתנים."""
    endpoints: set[str] = set()
    for swift_file in APP_SOURCES.rglob("*.swift"):
        text = swift_file.read_text()
        # כל ליטרל מחרוזת שנראה כמו נתיב API (כולל דרך משתנה/טרנרי).
        for literal in re.findall(r'"([a-z][a-z0-9\-/]*)"', text):
            endpoints.add("/" + literal.strip("/"))
        # נתיבים שמורכבים באינטרפולציה: "mobile/domains/\(domain.rawValue)" וכד'.
        for interpolated in re.finditer(r'"((?:[a-z0-9\-/]+)?)\\\(', text):
            prefix = interpolated.group(1).strip("/")
            if prefix:
                endpoints.add("/" + prefix + "/*")
    return endpoints


def route_is_used(route_path: str, app_endpoints: set[str]) -> bool:
    if route_path in app_endpoints:
        return True
    # התאמת נתיבים דינמיים: /finance-invoices-file/{row_id} ↔ /finance-invoices-file/*
    base = re.sub(r"\{[^}]+\}", "", route_path).rstrip("/")
    for endpoint in app_endpoints:
        if endpoint.endswith("/*") and base.startswith(endpoint[:-2].rstrip("/")):
            return True
    return False


def main() -> int:
    routes = load_server_routes()
    app_endpoints = collect_app_endpoints()
    exclusions: dict[str, str] = json.loads(EXCLUSIONS_FILE.read_text()) if EXCLUSIONS_FILE.exists() else {}

    used, excluded, gaps = [], [], []
    for route in routes:
        path = route["path"]
        if route_is_used(path, app_endpoints):
            used.append(path)
        elif path in exclusions:
            excluded.append((path, exclusions[path]))
        else:
            gaps.append(path)

    stale_exclusions = [p for p in exclusions if route_is_used(p, app_endpoints)]

    if "--report" in sys.argv:
        print(f"סה\"כ ראוטים בשרת: {len(routes)}")
        print(f"בשימוש באפליקציה: {len(used)}")
        print(f"מוחרגים בנימוק:  {len(excluded)}")
        print(f"פערים לא מטופלים: {len(gaps)}")
        if excluded:
            print("\n--- מוחרגים ---")
            for path, reason in sorted(excluded):
                print(f"  {path}  ← {reason}")

    if stale_exclusions:
        print("\n⚠️ החרגות מיותרות (הראוט כבר בשימוש — להסיר מהקובץ):")
        for path in stale_exclusions:
            print(f"  {path}")

    if gaps:
        print("\n❌ פערי פיצ'ר לא מטופלים — לממש באפליקציה או להחריג בנימוק ב-scripts/parity_exclusions.json:")
        for path in sorted(gaps):
            print(f"  {path}")
        return 1

    print("\n✅ ביקורת פאריטי עברה: כל ראוט בשרת בשימוש או מוחרג בנימוק.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
