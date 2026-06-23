from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.po_parser import parse_purchase_order
from services.parsers.common import extract_text_pdfplumber, fix_hebrew_text, normalize_ws


DEFAULT_SOURCE_ROOT = Path(
    "/Users/asafbeny/Library/Mobile Documents/com~apple~CloudDocs/Downloads/בן יעקב/מדבקות"
)
OUTPUT_JSON = PROJECT_ROOT / "logs" / "parser_audit_report.json"
OUTPUT_MD = PROJECT_ROOT / "logs" / "parser_audit_report.md"


PO_FILENAME_HINTS = (
    "po",
    "purchase order",
    "הזמנת רכש",
    "print purchase order",
    "zivpdf",
    "sivanb",
    "po_",
)
PO_TEXT_HINTS = (
    "הזמנת רכש",
    "purchase order",
    "מספר הזמנה",
    "po ",
    "po-",
    "po_",
)
NON_PO_FILENAME_HINTS = (
    "invoice",
    "חשבונית",
    "קבלה",
    "delivery",
    "תעודת משלוח",
    "מספר הובלה",
    "label",
    "coc",
    "packing",
    "mrb",
    "reportpage",
    "שליחות",
    "מדבקה",
    "allstickers",
    "כל המסמכים",
    "sticker",
    "label",
    "delivery",
)
HARD_NON_PO_FILENAME_HINTS = (
    "מספר הובלה",
    "label",
    "sticker",
    "delivery",
    "invoice",
    "חשבונית",
    "קבלה",
    "allstickers",
    "כל המסמכים",
    "coc",
    "mrb",
    "reportpage",
    "signed",
    "binder",
)
NON_PO_TEXT_HINTS = (
    "תעודת משלוח",
    "חשבונית מס",
    "חשבונית",
    "קבלה",
    "מספר הובלה",
    "certificate of conformity",
    "coc",
    "packing list",
)
HARD_NON_PO_TEXT_HINTS = (
    "תעודת משלוח",
    "חשבונית מס",
    "חשבונית",
    "קבלה",
)

PHONE_BLACKLIST = {
    "0547720142",
    "0505204010",
    "0503011503",
}


@dataclass
class AuditRow:
    path: str
    relative_path: str
    folder_customer: str
    document_type: str
    parser_name: str
    customer_name: str
    po_number: str
    po_date: str
    customer_id: str
    delivery_address: str
    contact_name: str
    contact_phone: str
    item_description: str
    item_quantity: float
    item_unit_price: float
    item_line_total: float
    subtotal: float
    vat: float
    total: float
    missing_fields: list[str]
    warnings: list[str]
    completeness_score: int
    preview: str


def iter_pdf_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() == ".pdf":
            yield path


def normalized_preview(text: str, limit: int = 220) -> str:
    text = normalize_ws(text or "")
    return text[:limit]


def classify_document(path: Path, raw_text: str, fixed_text: str) -> str:
    path_l = path.name.lower()
    file_text = f"{path_l} {path.stem.lower()}"
    path_text = path.as_posix().lower()
    fixed_l = fixed_text.lower()
    raw_l = raw_text.lower()
    basename = path.stem.lower()
    digits_only_name = basename.isdigit()
    starts_like_generated_doc = digits_only_name and (
        basename.startswith("250") or basename.startswith("550") or basename.startswith("850")
    )
    explicit_po_text = any(token in fixed_l or token in raw_l for token in PO_TEXT_HINTS)
    has_invoice_only_markers = "חשבון עסקה" in fixed_text or "חשבון עסקה" in raw_text
    internal_summary_doc = (
        "office@ben-yacov.com" in raw_l
        and "משרד:" in fixed_text
        and ("כתובת/אתר:" in fixed_text or "כתובת:" in fixed_text)
        and ("פרי ט:" in fixed_text or "פריט:" in fixed_text)
    )
    internal_spec_sheet = (
        "בן יעקב פתרונות טקסטיל" in fixed_text
        and ("משרד:" in fixed_text or "משרד" in fixed_text)
        and ("מפעל:" in fixed_text or "מפעל" in fixed_text)
        and (
            "מפרט מידות וכמויות מגיני דלתות" in fixed_text
            or "פרי ט:" in fixed_text
            or "פריט:" in fixed_text
            or "טק״מ" in fixed_text
        )
    )

    if internal_summary_doc or internal_spec_sheet:
        return "non_po"

    if has_invoice_only_markers and "הזמנת רכש" not in fixed_text and "הזמנת רכש" not in raw_text:
        return "non_po"

    if ("coc" in file_text or "מספר הובלה" in file_text or "binder" in file_text):
        return "non_po"

    if path.name.lower().startswith("binder") and "הזמנת רכש" not in fixed_text and "purchase order" not in fixed_l:
        return "non_po"

    if re.fullmatch(r"\d{2,3}-\d{2,3}", path.stem) and "משרד:" in fixed_text and "מפעל:" in fixed_text:
        return "non_po"

    if any(token in file_text for token in HARD_NON_PO_FILENAME_HINTS) and not explicit_po_text:
        return "non_po"

    leading_fixed = fixed_l[:450]
    leading_raw = raw_l[:450]
    if any(token in leading_fixed or token in leading_raw for token in HARD_NON_PO_TEXT_HINTS):
        return "non_po"

    if any(token in file_text for token in NON_PO_FILENAME_HINTS):
        if not explicit_po_text and not any(token in file_text for token in ("po", "purchase order", "הזמנת")):
            return "non_po"

    if any(token in fixed_l or token in raw_l for token in NON_PO_TEXT_HINTS):
        if not explicit_po_text:
            return "non_po"

    if starts_like_generated_doc and not explicit_po_text:
        return "non_po"

    if any(token in file_text for token in PO_FILENAME_HINTS):
        return "purchase_order"

    if explicit_po_text:
        return "purchase_order"

    return "unknown"


def normalize_phone(value: str) -> str:
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if digits.startswith("972") and len(digits) >= 12:
        digits = "0" + digits[3:]
    return digits


def collect_missing_fields(po) -> tuple[list[str], list[str]]:
    first_item = po.items[0] if po.items else None
    missing: list[str] = []
    warnings: list[str] = []

    if not po.customer_name:
        missing.append("customer_name")
    if not po.po_number:
        missing.append("po_number")
    if not po.po_date:
        missing.append("po_date")
    if not po.customer_id:
        missing.append("customer_id")
    if not po.delivery_address:
        missing.append("delivery_address")
    if not po.contact_name:
        missing.append("contact_name")
    if not po.contact_phone:
        missing.append("contact_phone")
    if not first_item or not first_item.description or first_item.description == "פריט לא זוהה":
        missing.append("item_description")
    if not first_item or not first_item.quantity or first_item.quantity <= 0:
        missing.append("item_quantity")
    if not first_item or first_item.line_total <= 0:
        missing.append("item_line_total")
    if po.total <= 0:
        missing.append("total")

    phone = normalize_phone(po.contact_phone)
    if phone and phone in PHONE_BLACKLIST:
        warnings.append("blacklisted_contact_phone")
    if phone and len(phone) not in {9, 10}:
        warnings.append("suspicious_contact_phone")
    if po.contact_name and "איש קשר" in po.contact_name:
        warnings.append("contact_name_contains_label")
    if po.delivery_address and "תאריך הדפסה" in po.delivery_address:
        warnings.append("delivery_address_contains_print_timestamp")
    if first_item and first_item.description:
        if len(first_item.description) > 180:
            warnings.append("item_description_too_long")
    if po.customer_name and len(po.customer_name) < 2:
        warnings.append("customer_name_too_short")

    return missing, warnings


def completeness_score(po, missing_fields: list[str], warnings: list[str]) -> int:
    score = 100
    missing_penalties = {
        "customer_name": 20,
        "po_number": 20,
        "po_date": 15,
        "customer_id": 12,
        "delivery_address": 12,
        "contact_name": 12,
        "contact_phone": 12,
        "item_description": 16,
        "item_quantity": 12,
        "item_line_total": 12,
        "total": 10,
    }
    warning_penalties = {
        "blacklisted_contact_phone": 18,
        "suspicious_contact_phone": 8,
        "contact_name_contains_label": 8,
        "delivery_address_contains_print_timestamp": 8,
        "item_description_too_long": 6,
        "customer_name_too_short": 5,
    }
    for field in missing_fields:
        score -= missing_penalties.get(field, 6)
    for warning in warnings:
        score -= warning_penalties.get(warning, 4)
    return max(0, score)


def audit_file(path: Path, root: Path) -> AuditRow | None:
    raw_text = extract_text_pdfplumber(path)
    fixed_text = fix_hebrew_text(raw_text)
    doc_type = classify_document(path, raw_text, fixed_text)

    if doc_type != "purchase_order":
        return None

    try:
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            po = parse_purchase_order(path)
    except Exception as exc:  # pragma: no cover - operational reporting
        preview = normalized_preview(fixed_text or raw_text)
        return AuditRow(
            path=str(path),
            relative_path=str(path.relative_to(root)),
            folder_customer=path.relative_to(root).parts[0] if path.relative_to(root).parts else "",
            document_type=doc_type,
            parser_name="error",
            customer_name="",
            po_number="",
            po_date="",
            customer_id="",
            delivery_address="",
            contact_name="",
            contact_phone="",
            item_description="",
            item_quantity=0,
            item_unit_price=0,
            item_line_total=0,
            subtotal=0,
            vat=0,
            total=0,
            missing_fields=["parse_exception"],
            warnings=[f"exception:{type(exc).__name__}", str(exc)],
            completeness_score=0,
            preview=preview,
        )

    if po is None:
        preview = normalized_preview(fixed_text or raw_text)
        return AuditRow(
            path=str(path),
            relative_path=str(path.relative_to(root)),
            folder_customer=path.relative_to(root).parts[0] if path.relative_to(root).parts else "",
            document_type=doc_type,
            parser_name="none",
            customer_name="",
            po_number="",
            po_date="",
            customer_id="",
            delivery_address="",
            contact_name="",
            contact_phone="",
            item_description="",
            item_quantity=0,
            item_unit_price=0,
            item_line_total=0,
            subtotal=0,
            vat=0,
            total=0,
            missing_fields=[
                "po_not_parsed",
                "customer_name",
                "po_number",
                "po_date",
                "customer_id",
                "delivery_address",
                "contact_name",
                "contact_phone",
                "item_description",
                "item_line_total",
                "total",
            ],
            warnings=[],
            completeness_score=0,
            preview=preview,
        )

    first_item = po.items[0] if po.items else None
    missing_fields, warnings = collect_missing_fields(po)
    score = completeness_score(po, missing_fields, warnings)
    preview = normalized_preview(fixed_text or raw_text)
    relative = path.relative_to(root)

    return AuditRow(
        path=str(path),
        relative_path=str(relative),
        folder_customer=relative.parts[0] if relative.parts else "",
        document_type=doc_type,
        parser_name=(po.extra or {}).get("parser_name", ""),
        customer_name=po.customer_name or "",
        po_number=po.po_number or "",
        po_date=po.po_date or "",
        customer_id=po.customer_id or "",
        delivery_address=po.delivery_address or "",
        contact_name=po.contact_name or "",
        contact_phone=po.contact_phone or "",
        item_description=first_item.description if first_item else "",
        item_quantity=first_item.quantity if first_item else 0,
        item_unit_price=first_item.unit_price if first_item else 0,
        item_line_total=first_item.line_total if first_item else 0,
        subtotal=po.subtotal or 0,
        vat=po.vat or 0,
        total=po.total or 0,
        missing_fields=missing_fields,
        warnings=warnings,
        completeness_score=score,
        preview=preview,
    )


def summarize(rows: list[AuditRow]) -> dict:
    parser_stats: dict[str, dict] = {}
    for parser_name, group in defaultdict(list, {}).items():
        parser_stats[parser_name] = group

    groups: dict[str, list[AuditRow]] = defaultdict(list)
    for row in rows:
        groups[row.parser_name or "unknown"].append(row)

    parser_summary = {}
    for parser_name, parser_rows in sorted(groups.items()):
        missing_counter: Counter[str] = Counter()
        warning_counter: Counter[str] = Counter()
        low_score = sorted(parser_rows, key=lambda item: (item.completeness_score, item.relative_path))[:8]
        for row in parser_rows:
            missing_counter.update(row.missing_fields)
            warning_counter.update(row.warnings)
        parser_summary[parser_name] = {
            "count": len(parser_rows),
            "average_score": round(sum(row.completeness_score for row in parser_rows) / len(parser_rows), 1),
            "missing_fields": dict(missing_counter.most_common()),
            "warnings": dict(warning_counter.most_common()),
            "worst_examples": [
                {
                    "relative_path": row.relative_path,
                    "customer_name": row.customer_name,
                    "po_number": row.po_number,
                    "score": row.completeness_score,
                    "missing_fields": row.missing_fields,
                    "warnings": row.warnings,
                }
                for row in low_score
            ],
        }

    folder_groups: dict[str, list[AuditRow]] = defaultdict(list)
    for row in rows:
        folder_groups[row.folder_customer].append(row)
    folder_summary = {
        folder: {
            "count": len(folder_rows),
            "average_score": round(sum(row.completeness_score for row in folder_rows) / len(folder_rows), 1),
            "parsers": dict(Counter(row.parser_name or "unknown" for row in folder_rows).most_common()),
        }
        for folder, folder_rows in sorted(folder_groups.items())
    }

    return {
        "total_purchase_orders": len(rows),
        "average_score": round(sum(row.completeness_score for row in rows) / len(rows), 1) if rows else 0,
        "parser_summary": parser_summary,
        "folder_summary": folder_summary,
    }


def build_markdown(summary: dict, rows: list[AuditRow], root: Path) -> str:
    low_rows = sorted(rows, key=lambda item: (item.completeness_score, item.relative_path))[:30]
    lines = [
        "# Parser Audit Report",
        "",
        f"- Source root: `{root}`",
        f"- Purchase-order candidates audited: **{summary['total_purchase_orders']}**",
        f"- Average completeness score: **{summary['average_score']}**",
        "",
        "## Parsers",
        "",
    ]
    for parser_name, data in summary["parser_summary"].items():
        lines.append(f"### {parser_name}")
        lines.append("")
        lines.append(f"- Files: **{data['count']}**")
        lines.append(f"- Average score: **{data['average_score']}**")
        if data["missing_fields"]:
            parts = ", ".join(f"`{name}` × {count}" for name, count in list(data["missing_fields"].items())[:8])
            lines.append(f"- Frequent missing fields: {parts}")
        if data["warnings"]:
            parts = ", ".join(f"`{name}` × {count}" for name, count in list(data["warnings"].items())[:8])
            lines.append(f"- Frequent warnings: {parts}")
        if data["worst_examples"]:
            lines.append("- Weakest examples:")
            for example in data["worst_examples"][:5]:
                details = ", ".join(example["missing_fields"] or example["warnings"] or ["no details"])
                label = example["po_number"] or "ללא מספר"
                lines.append(
                    f"  - `{example['relative_path']}` · {label} · score {example['score']} · {details}"
                )
        lines.append("")

    lines.append("## Lowest-Score Files")
    lines.append("")
    for row in low_rows:
        details = ", ".join(row.missing_fields or row.warnings or ["ok"])
        lines.append(
            f"- `{row.relative_path}` · parser `{row.parser_name or 'unknown'}` · score **{row.completeness_score}** · {details}"
        )
    lines.append("")
    return "\n".join(lines)


def main():
    source_root = Path(sys.argv[1]).expanduser() if len(sys.argv) > 1 else DEFAULT_SOURCE_ROOT
    if not source_root.exists():
        raise SystemExit(f"Source root not found: {source_root}")

    rows: list[AuditRow] = []
    inspected = 0
    for pdf_path in iter_pdf_files(source_root):
        inspected += 1
        row = audit_file(pdf_path, source_root)
        if row is not None:
            rows.append(row)

    summary = summarize(rows)
    payload = {
        "source_root": str(source_root),
        "inspected_pdf_count": inspected,
        "purchase_order_candidate_count": len(rows),
        "summary": summary,
        "rows": [row.__dict__ for row in rows],
    }
    OUTPUT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    OUTPUT_MD.write_text(build_markdown(summary, rows, source_root), encoding="utf-8")

    print(json.dumps(
        {
            "inspected_pdf_count": inspected,
            "purchase_order_candidate_count": len(rows),
            "average_score": summary["average_score"],
            "json_report": str(OUTPUT_JSON),
            "markdown_report": str(OUTPUT_MD),
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
