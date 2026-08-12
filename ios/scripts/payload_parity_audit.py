#!/usr/bin/env python3
"""ביקורת פאריטי של payload — משווה מה הדסקטופ שולח לכל endpoint מול מה שהאפליקציה שולחת.

הרעיון: ביקורת ה-route תופסת יכולת חסרה, אבל עיוורת לשדות חסרים בתוך בקשה
(כמו שדה percent שנעדר מהפקת קבלה). כאן מחלצים את מפתחות ה-JSON שהדסקטופ
שולח (templates/index_desktop.html) ואת המפתחות שהאפליקציה שולחת (קבצי Swift),
ומדווחים על כל מפתח שהדסקטופ שולח ולאפליקציה אין — אלא אם הוחרג בנימוק.
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
EXCLUSIONS_FILE = IOS_ROOT / "scripts" / "payload_parity_exclusions.json"


# ---------- חילוץ מפתחות מאובייקט־literal (JS או Swift) ----------

def extract_key_paths(text: str, js: bool) -> set[str]:
    """מחלץ נתיבי מפתחות (a, a.b) מתוך literal של אובייקט, בסריקה עמידה-לרעש."""
    paths: set[str] = set()
    stack: list[str | None] = []  # שם המפתח שהאובייקט הנוכחי הוא הערך שלו
    depth_names: list[str] = []
    i = 0
    pending_key: str | None = None
    expecting_value = False  # אחרי "key:" — המזהה הבא הוא ערך, לא מפתח shorthand
    key_re = re.compile(r'"?([A-Za-z_][A-Za-z0-9_]*)"?\s*:') if js else re.compile(r'"([A-Za-z_][A-Za-z0-9_]*)"\s*:')
    shorthand_re = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*(?=,|\})')

    while i < len(text):
        ch = text[i]
        if ch in "\"'":
            # דילוג על מחרוזות כדי לא לבלוע נקודתיים בתוכן
            quote = ch
            j = i + 1
            while j < len(text) and text[j] != quote:
                if text[j] == "\\":
                    j += 1
                j += 1
            segment = text[i:j + 1]
            match = key_re.match(text[i:])
            if match and text[i + match.end() - 1] == ":":
                key = match.group(1)
                prefix = ".".join(depth_names)
                paths.add(f"{prefix}.{key}" if prefix else key)
                pending_key = key
                i += match.end()
                continue
            i = j + 1
            continue
        if ch == "{" or ch == "[":
            depth_names.append(pending_key or "")
            depth_names = [n for n in depth_names]  # copy-on-write פשטות
            pending_key = None
            expecting_value = False
            i += 1
            continue
        if ch == "}" or ch == "]":
            if depth_names:
                depth_names.pop()
            i += 1
            continue
        match = key_re.match(text[i:])
        if match and not expecting_value:
            key = match.group(1)
            prefix = ".".join(n for n in depth_names if n)
            paths.add(f"{prefix}.{key}" if prefix else key)
            pending_key = key
            expecting_value = True
            i += match.end()
            continue
        if js and not expecting_value:
            match = shorthand_re.match(text[i:])
            if match and (i == 0 or text[i - 1] in "{, \n"):
                key = match.group(1)
                if key not in {"true", "false", "null"}:
                    prefix = ".".join(n for n in depth_names if n)
                    paths.add(f"{prefix}.{key}" if prefix else key)
                i += match.end()
                continue
        if ch == ",":
            expecting_value = False
        elif ch not in " \t\n" and expecting_value and not (key_re.match(text[i:]) or False):
            # מדלגים על תוכן הערך עד לפסיק/סוגר
            pass
        pending_key = None if ch in ",\n" else pending_key
        i += 1
    # מנקים עומק ראשון מדומה (ה-literal עצמו נפתח ב-{)
    cleaned = set()
    for path in paths:
        parts = [p for p in path.split(".") if p]
        cleaned.add(".".join(parts))
    return cleaned


def balanced_block(text: str, start: int, open_ch: str, close_ch: str) -> str:
    depth = 0
    i = start
    in_string: str | None = None
    while i < len(text):
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == in_string:
                in_string = None
        elif ch in "\"'":
            in_string = ch
        elif ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1
    return text[start:]


# ---------- צד הדסקטופ ----------

def desktop_payloads() -> dict[str, set[str]]:
    html = DESKTOP_HTML.read_text(encoding="utf-8")
    payloads: dict[str, set[str]] = {}

    # מפת השמות של payload שנבנה בהשמות (paymentPayload.check_number = ...)
    assigned: dict[str, set[str]] = {}
    for match in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]*)\.([a-z_][A-Za-z0-9_]*)\s*=', html):
        assigned.setdefault(match.group(1), set()).add(match.group(2))
    # וגם literal ראשוני: const paymentPayload = { ... }
    literal_init: dict[str, set[str]] = {}
    for match in re.finditer(r'\b(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{', html):
        block = balanced_block(html, match.end() - 1, "{", "}")
        literal_init[match.group(1)] = extract_key_paths(block, js=True)

    for match in re.finditer(r'fetch\(\s*[`"\']([^`"\']+)[`"\']', html):
        path = match.group(1).split("?")[0]
        if not path.startswith("/"):
            continue
        # מוגבל לבלוק הסוגריים של קריאת ה-fetch — שלא נזלוג לבקשה הבאה.
        call_block = balanced_block(html, match.start() + len("fetch"), "(", ")")
        keys: set[str] = set()
        stringify = re.search(r'JSON\.stringify\(\s*\{', call_block)
        if stringify:
            block = balanced_block(call_block, stringify.end() - 1, "{", "}")
            keys = extract_key_paths(block, js=True)
        else:
            # בקשת FormData: אוספים append-ים שנעשו לפני הקריאה.
            lookback = html[max(0, match.start() - 2000):match.start()]
            form_start = lookback.rfind("new FormData")
            if form_start == -1:
                continue
            for append_match in re.finditer(r'\.append\(\s*["\']([A-Za-z_][A-Za-z0-9_]*)["\']', lookback[form_start:]):
                keys.add(append_match.group(1))
            payloads.setdefault(path, set()).update(keys)
            continue
        block = call_block

        # הרחבת משתני-עזר: payment: paymentPayload → payment.check_number וכו'.
        # רק משתנים בעלי שם payload-י — הרחבה גורפת מציפה רעש מכל הקובץ.
        for var_match in re.finditer(r'([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([A-Za-z_][A-Za-z0-9_]*)\s*[,}]', block):
            key, var = var_match.group(1), var_match.group(2)
            # רק שמות מורכבים (paymentPayload) — "payload" גנרי שואב רעש מכל הקובץ.
            suffix = re.search(r'(Payload|Body|State)$', var)
            if not suffix or len(var) == len(suffix.group(1)):
                continue
            nested = assigned.get(var, set()) | literal_init.get(var, set())
            for sub in nested:
                keys.add(f"{key}.{sub}")

        payloads.setdefault(path, set()).update(keys)
    return payloads


# ---------- צד האפליקציה ----------

def app_payloads() -> dict[str, set[str]]:
    payloads: dict[str, set[str]] = {}
    for swift in SWIFT_DIR.rglob("*.swift"):
        if "MockTransport" in swift.name:
            continue
        text = swift.read_text(encoding="utf-8")

        # מילונים שנבנים במשתנה מקומי (var payment: [String: Any] = [...] + payment["x"] =)
        var_keys: dict[str, set[str]] = {}
        for var_match in re.finditer(r'(?:var|let)\s+(\w+)\s*:\s*\[String:\s*Any\]\s*=\s*\[', text):
            block = balanced_block(text, var_match.end() - 1, "[", "]")
            var_keys.setdefault(var_match.group(1), set()).update(extract_key_paths(block, js=False))
        for assign_match in re.finditer(r'(\w+)\["(\w+)"\]\s*=', text):
            var_keys.setdefault(assign_match.group(1), set()).add(assign_match.group(2))

        for match in re.finditer(r'postJSON\(\s*"([^"]+)"\s*,\s*body:\s*\[', text):
            path = "/" + match.group(1).lstrip("/")
            block = balanced_block(text, match.end() - 1, "[", "]")
            keys = extract_key_paths(block, js=False)
            # הרחבה: "payment": payment → payment.<keys של המשתנה>
            for ref in re.finditer(r'"(\w+)":\s*(\w+)\s*[,\]]', block):
                key, var = ref.group(1), ref.group(2)
                for sub in var_keys.get(var, set()):
                    keys.add(f"{key}.{sub}")
            payloads.setdefault(path, set()).update(keys)
        for match in re.finditer(r'postMultipart\(\s*"([^"]+)"[^)]*?fields:\s*\[', text, re.S):
            path = "/" + match.group(1).lstrip("/")
            block = balanced_block(text, match.end() - 1, "[", "]")
            payloads.setdefault(path, set()).update(extract_key_paths(block, js=False))
        # שדות קבצים (MultipartFile(field: "file")) — חלק מה-payload לכל דבר.
        for match in re.finditer(r'postMultipart\(\s*"([^"]+)"', text):
            path = "/" + match.group(1).lstrip("/")
            tail = text[match.end():match.end() + 800]
            for file_match in re.finditer(r'MultipartFile\(field:\s*"([^"]+)"', tail):
                payloads.setdefault(path, set()).add(file_match.group(1))
    return payloads


# מפתחות שהם רעש DOM/JS ולא שדות בקשה.
NOISE_KEYS = {
    "innerHTML", "className", "textContent", "style", "dataset", "disabled",
    "value", "id", "onclick", "checked", "length", "console",
}


def is_noise(key: str) -> bool:
    parts = key.split(".")
    return any(part in NOISE_KEYS for part in parts) or any(not part.islower() and "_" not in part and len(part) > 1 and not part.islower() for part in [parts[-1]]) and parts[-1][0].isupper()


def main() -> int:
    exclusions: dict[str, str] = {}
    if EXCLUSIONS_FILE.exists():
        exclusions = json.loads(EXCLUSIONS_FILE.read_text(encoding="utf-8"))

    desktop = desktop_payloads()
    app = app_payloads()
    shared = sorted(set(desktop) & set(app))

    gaps: list[str] = []
    used_exclusions: set[str] = set()
    for path in shared:
        missing = {k for k in desktop[path] - app[path] if not is_noise(k)}
        for key in sorted(missing):
            token = f"{path}::{key}"
            if token in exclusions:
                used_exclusions.add(token)
                continue
            gaps.append(token)

    stale = [token for token in exclusions if token not in used_exclusions]

    # endpoints "אטומים": הדסקטופ שולח משתנה (row/data/visit) בלי מפתחות פנימיים —
    # הביקורת עיוורת לתוכן, אז מציפים אותם כאזהרה לבדיקה ידנית תקופתית.
    OPAQUE_KEYS = {"row", "data", "visit", "customer", "labels", "payment", "invoice", "withholding"}
    opaque = []
    for path in shared:
        bare = {k for k in desktop[path] if k in OPAQUE_KEYS}
        nested_prefixes = {k.split(".")[0] for k in desktop[path] if "." in k}
        fully_opaque = bare - nested_prefixes
        if fully_opaque:
            opaque.append(f"{path} ({', '.join(sorted(fully_opaque))})")

    print(f"🔎 פאריטי payload: {len(shared)} endpoints משותפים לדסקטופ ולאפליקציה")
    if gaps:
        print("\n❌ מפתחות שהדסקטופ שולח והאפליקציה לא (endpoint::key):")
        for gap in gaps:
            print(f"  {gap}")
    if stale:
        print("\n⚠️ החרגות מיותרות (המפתח כבר נשלח או שה-endpoint לא משותף — להסיר):")
        for token in sorted(stale):
            print(f"  {token}")
    if opaque:
        print("\n👁 endpoints אטומים לחילוץ (הדסקטופ שולח משתנה שלם — להשוות ידנית):")
        for item in opaque:
            print(f"  {item}")
    if not gaps:
        print("✅ אין פערי payload לא מוסברים.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
