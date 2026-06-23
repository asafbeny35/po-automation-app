from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IS_VERCEL = str(os.getenv("VERCEL", "") or "").strip() == "1"


def runtime_root() -> Path:
    configured = str(os.getenv("PO_RUNTIME_ROOT", "") or "").strip()
    if configured:
        root = Path(configured)
    elif IS_VERCEL:
        root = Path("/tmp/po_automation_app")
    else:
        root = PROJECT_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


def runtime_path(*parts: str) -> Path:
    target = runtime_root().joinpath(*parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def project_path(*parts: str) -> Path:
    return PROJECT_ROOT.joinpath(*parts)
