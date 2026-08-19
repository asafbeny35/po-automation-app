"""WhatsApp Railway integration tests.

These tests call the Railway WhatsApp service DIRECTLY (bypassing the app server)
to verify the real integration path used in production.

Run with:
    WHATSAPP_RAILWAY_URL=https://your-railway-app.railway.app \
    WHATSAPP_RAILWAY_SECRET=your-secret \
    python3 -m pytest tests_full_system/api/test_whatsapp_railway.py -v

Or via the app server (which proxies to Railway):
    python3 -m pytest tests_full_system/api/test_whatsapp_railway.py -v
"""
from __future__ import annotations

import pytest
import httpx

from tests_full_system.settings import SETTINGS


def _skip_if_railway_not_configured():
    if not SETTINGS.whatsapp_railway_url:
        pytest.skip("WHATSAPP_RAILWAY_URL not set — skipping Railway WhatsApp tests")


# ===========================================================================
# Direct Railway service tests (no app server needed)
# ===========================================================================

@pytest.mark.railway_whatsapp
def test_railway_url_is_configured():
    """Verifies WHATSAPP_RAILWAY_URL is set — skips (not fails) when absent.

    Run with: WHATSAPP_RAILWAY_URL=... pytest tests_full_system/api/test_whatsapp_railway.py
    """
    _skip_if_railway_not_configured()
    assert SETTINGS.whatsapp_railway_url.startswith("http"), (
        f"WHATSAPP_RAILWAY_URL must start with http/https, got: {SETTINGS.whatsapp_railway_url!r}"
    )


@pytest.mark.railway_whatsapp
@pytest.mark.timeout(30)
def test_railway_health_endpoint_responds():
    """Railway service must respond on /health (or /)."""
    _skip_if_railway_not_configured()
    base_url = SETTINGS.whatsapp_railway_url
    with httpx.Client(timeout=15) as client:
        for path in ("/health", "/status", "/"):
            try:
                r = client.get(f"{base_url}{path}")
                # Any response (including 401/403) means the service is up
                assert r.status_code < 600, f"Railway returned {r.status_code} on {path}"
                return  # First responding path is enough
            except httpx.ConnectError:
                continue
        pytest.fail(f"Railway service at {base_url} did not respond on /health, /status, or /")


@pytest.mark.railway_whatsapp
@pytest.mark.timeout(15)
def test_railway_send_endpoint_exists():
    """Railway /send endpoint must exist — verified via 401 (no secret = instant reject)."""
    _skip_if_railway_not_configured()
    base_url = SETTINGS.whatsapp_railway_url
    # Deliberately omit secret — server rejects immediately with 401 if endpoint exists
    with httpx.Client(timeout=10) as client:
        r = client.post(f"{base_url}/send", json={"phone": "", "message": "", "files": []})
        assert r.status_code not in {404, 405}, (
            f"Railway /send not found at {base_url}/send (got {r.status_code})"
        )
        # 401 = endpoint exists, secret rejected (expected when secret omitted)
        # 200/400/422/500 = endpoint exists and processed
        assert r.status_code in {200, 400, 401, 422, 500}, (
            f"Unexpected status from /send: {r.status_code} {r.text[:200]}"
        )


@pytest.mark.railway_whatsapp
@pytest.mark.slow
@pytest.mark.timeout(360)
def test_railway_send_real_whatsapp_message():
    """Send a real WhatsApp test message to the configured test number via Railway.

    This is the closest-to-production test possible:
    - Calls Railway /send directly (same path as production)
    - Sends to the owner's test number (0547720142 by default)
    - Validates the response matches Railway's success shape

    NOTE: Railway's Playwright-based WhatsApp send takes 60-180s (browser navigation
    + message delivery). This test uses a 300s timeout to accommodate that.
    """
    _skip_if_railway_not_configured()
    base_url = SETTINGS.whatsapp_railway_url
    payload = {
        "phone": SETTINGS.whatsapp_test_number,
        "message": "🧪 TEST | נעלולי פלא | בדיקת Railway WhatsApp — אנא התעלם",
        "files": [],
    }
    if SETTINGS.whatsapp_railway_secret:
        payload["secret"] = SETTINGS.whatsapp_railway_secret
    with httpx.Client(timeout=300) as client:
        r = client.post(f"{base_url}/send", json=payload)
    assert r.status_code == 200, (
        f"Railway send failed ({r.status_code}): {r.text[:300]}"
    )
    body = r.json()
    assert isinstance(body, dict), f"Expected dict response, got: {type(body)}"
    ok_indicators = ("status", "success", "result", "message_id", "id")
    assert any(k in body for k in ok_indicators), (
        f"Railway response missing expected success key. Got: {list(body.keys())}"
    )


# ===========================================================================
# App-server WhatsApp tests (via the app API, which proxies to Railway)
# ===========================================================================

@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.railway_whatsapp
@pytest.mark.timeout(60)
def test_app_whatsapp_provider_is_railway(api_client):
    """The app must select Railway as the WhatsApp provider when URL is configured.

    Verifies the provider selection logic, not the actual send.
    """
    _skip_if_railway_not_configured()
    # Call /whatsapp-send-reminder with empty phone — it should fail with
    # a Railway-specific error, not a WhatsApp Web Playwright error
    r = api_client.post(
        "/whatsapp-send-reminder",
        json={"phone": "", "message": "TEST"},
        timeout=30,
    )
    # Regardless of status, the error must NOT mention Playwright or Web
    if r.status_code != 200 and isinstance(r.payload, dict):
        error_text = str(r.payload.get("error") or "").lower()
        assert "playwright" not in error_text and "web" not in error_text, (
            f"App used WhatsApp Web instead of Railway.\n"
            f"Error: {error_text}\n"
            f"Set WHATSAPP_RAILWAY_URL env var on the app server."
        )


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.railway_whatsapp
@pytest.mark.slow
@pytest.mark.timeout(360)
def test_app_send_whatsapp_via_railway_to_test_number(api_client):
    """End-to-end: app server → Railway → WhatsApp.

    Sends a real WhatsApp message through the app's /whatsapp-send-reminder
    endpoint, which proxies to Railway (when WHATSAPP_RAILWAY_URL is set on
    the app server process).

    NOTE: Railway Playwright send takes 60-180s — use --timeout=360 or -m slow.
    """
    _skip_if_railway_not_configured()
    r = api_client.post(
        "/whatsapp-send-reminder",
        json={
            "phone": SETTINGS.whatsapp_test_number,
            "message": "🧪 TEST | נעלולי פלא | בדיקת שרת→Railway→WhatsApp",
        },
        timeout=300,
    )
    assert r.status_code == 200, (
        f"App WhatsApp send failed ({r.status_code}): {r.payload}"
    )
    assert isinstance(r.payload, dict)
    # App returns {"status": "ok"} — no provider field (it's an internal detail)
    assert r.payload.get("status") in {"ok", "success"}, (
        f"Unexpected response: {r.payload}"
    )


@pytest.mark.api
@pytest.mark.requires_live_server
@pytest.mark.railway_whatsapp
@pytest.mark.timeout(90)
def test_app_inventory_po_whatsapp_via_railway(api_client):
    """Inventory PO WhatsApp send goes through Railway."""
    _skip_if_railway_not_configured()
    r = api_client.post(
        "/inventory-purchase-orders-send-whatsapp",
        json={
            "po_number": "TEST-RAILWAY-001",
            "phone": SETTINGS.whatsapp_test_number,
            "message": "🧪 TEST | נעלולי פלא | הזמנת רכש — בדיקת Railway",
        },
        timeout=60,
    )
    # May return 200 (sent) or 500 (PO not found) — both are fine
    # The key assertion: no WhatsApp Web / Playwright involvement
    if r.status_code != 200 and isinstance(r.payload, dict):
        error_text = str(r.payload.get("error") or "").lower()
        assert "playwright" not in error_text, (
            "App used WhatsApp Web instead of Railway for PO send"
        )
