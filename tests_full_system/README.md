# Full System Test Suite

This folder contains the full test code scaffold for the entire `PO Automation` system.

## Safety defaults
- Document creation tests are written for `Sandbox` only.
- No test is allowed to intentionally create documents in `GreenInvoice PROD`.
- Any WhatsApp-related test data is hard-bound to `0547720142`.
- Tests are designed to create clearly marked `TEST` entities.

## Structure
- `api/` HTTP and route-contract tests
- `e2e/` end-to-end browser tests
- `page_objects/` Playwright page objects
- `unit/` guardrail, manifest, and pure logic tests
- `helpers/` shared auth, browser, API, waits, builders
- `manifests/` route, tab, and flow coverage registry

## Intended execution model
- API tests: run against a local server or a direct test harness
- E2E tests: run against `http://localhost:8000` with an authenticated browser storage state
- Integration-sensitive tests rely on environment variables instead of hard-coded secrets

## Important
This suite is intentionally created without running it yet. Before first execution:
- install test dependencies
- configure environment variables
- prepare authenticated storage state for browser tests
- verify Gmail/Drive/Sheets/WhatsApp sandbox-safe configuration
- read the pre-run and cleanup strategy:
  - `/Users/asafbeny/Downloads/po_automation_app/TEST_PRE_RUN_AND_CLEANUP_STRATEGY.md`

## Suggested next step before first run
1. Install `requirements-test.txt`
2. Create a dedicated authenticated browser storage-state file
3. Dry-run only:
   - unit tests
   - manifest integrity
   - route smoke
4. Then gradually enable API and E2E groups

## Cleanup
- Dry-run cleanup report:
  - `python /Users/asafbeny/Downloads/po_automation_app/tests_full_system/run_cleanup.py`
- Apply cleanup for `TEST` / `נעלולי פלא` entities:
  - `python /Users/asafbeny/Downloads/po_automation_app/tests_full_system/run_cleanup.py --apply`
