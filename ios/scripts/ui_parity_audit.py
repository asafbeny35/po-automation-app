#!/usr/bin/env python3
"""ביקורת פאריטי של פקדי UI — כל פקד אינטראקטיבי בדסקטופ חייב מקבילה באפליקציה.

הרעיון: פערים כמו כפתורי הסינון של גבייה/תשלום לא נראים בשום route — הם UI
טהור. כאן מחלצים מהדסקטופ את משפחות הפקדים המוצהרות (data-* על כפתורים,
טוגלים וסלקטים עם id), ולכל משפחה דורשים או מיפוי ל-accessibility identifier
קיים באפליקציה, או החרגה מנומקת. משפחה חדשה בדסקטופ בלי מיפוי = הבילד נכשל.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

IOS_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = IOS_ROOT.parent
DESKTOP_HTML = REPO_ROOT / "templates" / "index_desktop.html"
SWIFT_DIR = IOS_ROOT / "BenYacovManage"
MAP_FILE = IOS_ROOT / "scripts" / "ui_parity_map.json"


def desktop_control_families() -> dict[str, set[str]]:
    """משפחות פקדים בדסקטופ: data-<family> → סט הערכים שלהן."""
    html = DESKTOP_HTML.read_text(encoding="utf-8")
    families: dict[str, set[str]] = {}
    # data-attributes על אלמנטים אינטראקטיביים (button/select/input/label/span-כפתורי)
    for match in re.finditer(r'<(?:button|select|input|a|span|div)[^>]*?\bdata-([a-z][a-z0-9-]*)="([^"]*)"', html):
        family, value = match.group(1), match.group(2)
        families.setdefault(family, set()).add(value)
    # טוגלים וסלקטים עם id — כל אחד הוא פקד החלטה בפני עצמו, לכן כל id
    # הוא token נפרד (קיבוץ למשפחה אחת הסתיר את financeInvoiceParseUnpaidToggle).
    for match in re.finditer(r'<input[^>]*\btype="checkbox"[^>]*\bid="([A-Za-z0-9_-]+)"', html):
        families.setdefault(f"checkbox:{match.group(1)}", set()).add(match.group(1))
    for match in re.finditer(r'<select[^>]*\bid="([A-Za-z0-9_-]+)"', html):
        families.setdefault(f"select:{match.group(1)}", set()).add(match.group(1))
    return families


def app_identifiers() -> set[str]:
    identifiers: set[str] = set()
    for swift in SWIFT_DIR.rglob("*.swift"):
        text = swift.read_text(encoding="utf-8")
        for match in re.finditer(r'accessibilityIdentifier\("([^"]+)"\)', text):
            identifiers.add(match.group(1))
        # מזהים שמועברים כפרמטר לפונקציות עזר (actionRow/uploadButton/statusChip/גיליונות שליחה)
        for match in re.finditer(r'\b(?:id|submitID):\s*"([^"]+)"', text):
            identifiers.add(match.group(1))
        # מזהים עם אינטרפולציה — שומרים את הקידומת (payments-status-\(x) → payments-status-)
        for match in re.finditer(r'accessibilityIdentifier\("([^"\\]+)\\\(', text):
            identifiers.add(match.group(1) + "*")
    return identifiers


def identifier_exists(identifier: str, identifiers: set[str]) -> bool:
    if identifier in identifiers:
        return True
    return any(
        candidate.endswith("*") and identifier.startswith(candidate[:-1])
        for candidate in identifiers
    )


def main() -> int:
    mapping: dict[str, str] = {}
    if MAP_FILE.exists():
        mapping = json.loads(MAP_FILE.read_text(encoding="utf-8"))

    families = desktop_control_families()
    identifiers = app_identifiers()

    problems: list[str] = []
    unmapped: list[str] = []
    used: set[str] = set()

    for family in sorted(families):
        token = family if family.startswith(("checkbox:", "select:")) else f"data-{family}"
        entry = mapping.get(token)
        if entry is None:
            values = sorted(families[family])
            preview = ", ".join(values[:6]) + ("…" if len(values) > 6 else "")
            unmapped.append(f"{token} ({len(values)} ערכים: {preview})")
            continue
        used.add(token)
        # ערך המיפוי: "app:<identifier>" (חייב להתקיים בקוד) או נימוק חופשי להחרגה.
        if entry.startswith("app:"):
            identifier = entry[4:]
            if not identifier_exists(identifier, identifiers):
                problems.append(f"{token} ממופה ל-'{identifier}' אבל המזהה לא קיים באפליקציה")

    stale = [token for token in mapping if token not in used]

    print(f"🔎 פאריטי פקדי UI: {len(families)} משפחות פקדים בדסקטופ, {len(identifiers)} מזהי אפליקציה")
    if unmapped:
        print("\n❌ משפחות פקדים בלי מיפוי או החרגה (להוסיף ל-ui_parity_map.json):")
        for item in unmapped:
            print(f"  {item}")
    if problems:
        print("\n❌ מיפויים שבורים:")
        for item in problems:
            print(f"  {item}")
    if stale:
        print("\n⚠️ מיפויים למשפחות שכבר לא קיימות בדסקטופ (להסיר):")
        for token in sorted(stale):
            print(f"  {token}")
    if not unmapped and not problems:
        print("✅ כל פקדי הדסקטופ ממופים או מוחרגים בנימוק.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
