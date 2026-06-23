# Deployment Split

## Goal

Run the shared FastAPI backend outside the local Mac, while keeping browser-dependent automations out of the serverless runtime.

## Current Vercel Scope

The Vercel deployment path is intended for:

- FastAPI routes
- HTML/Jinja screens
- Supabase-backed business data
- read/write APIs that do not require a persistent local browser profile

## Not Suitable For Vercel Function Runtime

These flows should stay in a separate worker/runtime:

- WhatsApp Web automation
- Playwright flows that depend on persistent authenticated browser state
- local-file heavy batch generation that assumes a stable writable filesystem

## Practical Split

1. `po_automation_app` on Vercel
   - public/admin web UI
   - mobile JSON endpoints
   - Supabase-backed repositories
2. automation worker on a persistent host
   - Playwright / WhatsApp
   - long-running browser sessions
   - document/attachment send orchestration

## Files Added

- `.vercelignore`
- `vercel.json`

## Next Runtime Step

Before a production deploy, move the remaining browser-dependent routes behind an internal worker boundary so the Vercel-hosted backend can call them asynchronously instead of trying to execute them inline.
