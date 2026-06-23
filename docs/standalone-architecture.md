# BenYacovOrders Standalone Architecture

## Target

The system must stop depending on the local Mac as its runtime host.

Required end state:

- The desktop/web client is a standalone hosted client.
- The iPhone app is a standalone client.
- Both clients work against the same centralized backend and the same Supabase project.
- Google Sheets, local JSON caches, and browser `localStorage` are not the operational source of truth.

## Correct split

### 1. Supabase

Supabase is the system of record for:

- customers
- order / quote / working-order history
- delivery confirmations / contacts
- marketing
- finance invoices / withholding / settings
- HR structured data
- payments-transfer shared snapshot and future row model

Supabase Storage should become the canonical store for uploaded/generated files over time.

### 2. Hosted API / orchestration backend

The backend remains responsible for privileged integrations:

- Green Invoice
- Gmail / Google Drive
- parser execution
- PDF generation
- operational workflows

This backend must be hosted, not tied to `localhost`.

### 3. Automation worker

WhatsApp Web / Playwright / persistent browser automation should be moved to a dedicated always-on worker.

Reason:

- function-style hosting is fine for API calls and normal backend routes
- persistent browser automation is a different runtime concern
- it needs durable browser state, filesystem/session handling, and longer-lived execution

## What is already true

- Supabase project exists and is active.
- Most structured business domains already have Supabase tables.
- Backend config already supports `DATA_BACKEND=supabase`.

## What was still wrong before this tranche

- `finance_settings` was still not reading/writing through Supabase.
- `payments_transfer` shared state still lived only in local disk cache.
- The iPhone app was still effectively coupled to a locally hosted web runtime.
- Many flows still rely on:
  - Google Sheets
  - local JSON cache files
  - local uploaded files
  - browser `localStorage`
  - local OAuth token files
  - local Playwright browser profiles

## What this tranche changed

- `finance_settings` now reads/writes through Supabase `app_settings`.
- `payments_transfer` snapshot cache now persists to Supabase `payments_transfer_snapshots` in addition to local disk fallback.

## Next tranche

1. Move remaining structured domains that still depend on Sheets/disk:
   - pazomat
   - sibus
   - inventory / pricing / supplier delivery notes
   - payments-transfer row mutations
2. Replace server-side local file assumptions with Supabase Storage-backed metadata.
3. Stop using browser `localStorage` for authoritative business state.
4. Split hosted API from automation worker.
5. Point both desktop/web and iPhone app to the hosted backend instead of `localhost`.
