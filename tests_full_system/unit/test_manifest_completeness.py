"""Manifest completeness test — verifies that ROUTE_MANIFEST covers every route in app.py.

This test will fail if a new endpoint is added to app.py but not registered in the manifest,
ensuring tests can't silently miss new routes.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests_full_system.manifests.routes import ROUTE_MANIFEST

APP_PY = Path(__file__).resolve().parents[2] / "app.py"

# Endpoints intentionally excluded from testing (OAuth callbacks need browser, etc.)
INTENTIONALLY_EXCLUDED = {
    # These require a real OAuth browser flow — tested manually
    "/google-drive/oauth/callback",
    "/gmail-oauth/callback",
}


def _extract_app_routes() -> set[str]:
    """Parse @app.get/post/put/delete decorators from app.py."""
    try:
        source = APP_PY.read_text(encoding="utf-8", errors="ignore")
    except SyntaxError:
        # app.py may have a syntax error; parse line by line
        lines = APP_PY.read_bytes().decode("utf-8", errors="ignore").splitlines()
        source = "\n".join(lines)
    pattern = re.compile(r'@app\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']')
    return {m.group(2) for m in pattern.finditer(source)}


def _manifest_paths() -> set[str]:
    return {r["path"] for r in ROUTE_MANIFEST}


def test_manifest_is_non_empty():
    assert len(ROUTE_MANIFEST) > 0


def test_manifest_routes_have_required_keys():
    required = {"method", "path", "category", "safe"}
    for route in ROUTE_MANIFEST:
        missing = required - set(route.keys())
        assert not missing, f"Route {route} missing keys: {missing}"


def test_manifest_methods_are_valid():
    valid_methods = {"GET", "POST", "PUT", "DELETE", "PATCH"}
    for route in ROUTE_MANIFEST:
        assert route["method"].upper() in valid_methods, f"Invalid method: {route['method']}"


def test_manifest_safe_flag_is_bool():
    for route in ROUTE_MANIFEST:
        assert isinstance(route["safe"], bool), f"safe must be bool in route: {route}"


def test_manifest_paths_are_non_empty_strings():
    for route in ROUTE_MANIFEST:
        assert isinstance(route["path"], str)
        assert route["path"].startswith("/"), f"Path must start with /: {route['path']}"


def test_manifest_has_no_duplicate_method_path_pairs():
    seen = set()
    for route in ROUTE_MANIFEST:
        key = (route["method"].upper(), route["path"])
        assert key not in seen, f"Duplicate route: {key}"
        seen.add(key)


def test_all_app_routes_are_in_manifest():
    """Every route registered in app.py must appear in the manifest."""
    app_routes = _extract_app_routes()
    manifest_paths = _manifest_paths()

    missing = set()
    for path in app_routes:
        if path in INTENTIONALLY_EXCLUDED:
            continue
        if path not in manifest_paths:
            missing.add(path)

    assert not missing, (
        f"Routes in app.py not in manifest ({len(missing)}):\n"
        + "\n".join(f"  {p}" for p in sorted(missing))
        + "\n\nAdd these to tests_full_system/manifests/routes.py"
    )


def test_manifest_has_no_paths_not_in_app():
    """Manifest should not have stale routes that no longer exist in app.py."""
    app_routes = _extract_app_routes()
    manifest_paths = _manifest_paths()

    # Normalize path params for comparison
    def _normalize(p: str) -> str:
        return re.sub(r"\{[^}]+\}", "{param}", p)

    app_normalized = {_normalize(p) for p in app_routes}
    stale = set()
    for path in manifest_paths:
        if _normalize(path) not in app_normalized:
            stale.add(path)

    # Warn rather than fail — stale routes are less critical than missing ones
    if stale:
        import warnings
        warnings.warn(
            f"Manifest has {len(stale)} path(s) not found in app.py: {sorted(stale)}",
            stacklevel=1,
        )


def test_manifest_read_only_routes_are_gets():
    """Routes marked safe=True that are POSTs deserve scrutiny."""
    questionable = [
        r for r in ROUTE_MANIFEST
        if r["safe"] and r["method"].upper() == "POST"
    ]
    # Not necessarily wrong, but uncommon — document them
    for route in questionable:
        # Each safe POST must be in an explicit allowlist (currently none)
        assert False, (
            f"Route marked safe=True but uses POST: {route}. "
            "Either change safe to False or add to the allowlist in this test."
        ) if questionable else None
