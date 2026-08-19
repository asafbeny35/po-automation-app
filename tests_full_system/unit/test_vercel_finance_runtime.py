import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_vercel_python_function_does_not_force_legacy_50mb_bundle() -> None:
    config = json.loads((PROJECT_ROOT / "vercel.json").read_text(encoding="utf-8"))
    python_build = next(
        build
        for build in config.get("builds") or []
        if build.get("src") == "api/index.py"
    )

    assert "maxLambdaSize" not in (python_build.get("config") or {})


def test_finance_invoice_save_handles_non_json_server_responses() -> None:
    template = (PROJECT_ROOT / "templates" / "index_desktop.html").read_text(encoding="utf-8")

    assert "async function parseFinanceInvoiceSaveResponse(response)" in template
    assert template.count("const payload = await parseFinanceInvoiceSaveResponse(response);") == 2
    assert template.count('const response = await fetch("/finance-invoices-save"') == 2
