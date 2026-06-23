## Ben Yacov Orders: iOS + Supabase Migration

### Goal

Create a new iPhone app that covers the existing local order-management system, while moving the shared operational data into Supabase so the local FastAPI app and the iOS app both use the same database.

### Current system reality

The current app is not a small PO uploader anymore. It is a multi-domain internal system with these active domains:

- Orders and quote history
- Working orders
- Delivery confirmations
- Customers
- Project managers
- Marketing pipeline, reminders, notes, work managers, construction companies
- Finance invoices and customer withholdings
- Payments and transfers
- HR employees, hours, payroll, documents, payslip prep history
- Drive/Gmail/WhatsApp/Green Invoice integrations

Persistence is currently split between:

- Google Sheets tabs
- Local JSON caches
- Local uploaded files
- Google Drive folders/files

### Target architecture

#### Shared data layer

Supabase becomes the canonical operational database for structured business data.

#### Local app role

The existing FastAPI app remains the privileged orchestration layer for:

- Green Invoice API calls
- Gmail sending and OAuth
- Google Drive sync
- WhatsApp browser automation
- PDF generation and parser execution

The local app will gradually stop treating Google Sheets as the main source of truth and instead read/write Supabase.

#### iOS app role

The iOS app will focus first on:

- Viewing operational state
- Customer lookup
- Order/quote history
- Finance and payment visibility
- HR overview
- Triggering safe workflows through the backend

Direct mobile writes to Supabase should be limited to authenticated internal users and only for domains that are safe for mobile editing.

### Migration strategy

#### Phase 1

- Mirror the current Google Sheets/JSON domains into Supabase tables with minimal structural change
- Keep the existing FastAPI app alive
- Add configuration for a switchable persistence backend
- Generate a canonical export from the current caches/sheets

#### Phase 2

- Build the new iOS shell with all main tabs
- Connect read-only module views to Supabase
- Add authenticated internal access

#### Phase 3

- Move write operations from Sheets to Supabase
- Keep Google Sheets only as export/reporting if still needed
- Route privileged actions through backend endpoints

#### Phase 4

- Replace JSON cache dependency with Supabase-backed repositories
- Add realtime refresh where it helps operations

### Domain mapping

| Existing source | Shared target |
| --- | --- |
| `customers_cache.json` | `public.customers` |
| `order_history_cache.json` | `public.order_history` |
| `quote_history_cache.json` | `public.quote_history` |
| `working_orders_cache.json` | `public.working_orders` |
| `delivery_confirmations_cache.json` | `public.delivery_confirmations` |
| `delivery_contacts_cache.json` | `public.delivery_contacts` |
| `project_managers_cache.json` | `public.project_managers` |
| `marketing_pipeline_cache.json` | `public.marketing_pipeline` |
| `marketing_history_cache.json` | `public.marketing_history` |
| `marketing_reminders_cache.json` | `public.marketing_reminders` |
| `marketing_work_managers_cache.json` | `public.marketing_work_managers` |
| `marketing_construction_companies_cache.json` | `public.marketing_construction_companies` |
| `finance_invoices_cache.json` | `public.finance_invoices` |
| `finance_customer_withholdings_cache.json` | `public.finance_customer_withholdings` |
| `finance_bank_movements_cache.json` | `public.finance_bank_movements` |
| `payments_transfer_cache.json` | `public.payments_transfer_snapshots` |
| `hr_employees_cache.json` | `public.hr_employees` |
| `hr_hours_cache.json` | `public.hr_hours` |
| `hr_payroll_cache.json` | `public.hr_payroll` |
| `hr_contributions_cache.json` | `public.hr_contributions` |
| `hr_documents_cache.json` | `public.hr_documents` |
| `hr_payslip_prep_history_cache.json` | `public.hr_payslip_prep_history` |

### Security model

- No anonymous access to operational tables
- All exposed tables use RLS
- Access is restricted to authenticated internal users
- Privileged integrations stay server-side in FastAPI

### File strategy

Structured data belongs in Supabase tables.

Binary assets should move to Supabase Storage over time, but existing Google Drive links should be preserved during transition so current flows do not break.

### What is already prepared in this branch

- Initial Supabase schema draft
- Export script from current caches to canonical seed files
- iOS project shell with all major tabs
- Local config placeholders for Supabase/backend switching

### Current status

- Supabase project created: `vfmrsljkdwgshclqrmiw`
- Initial schema applied successfully
- Seed data imported into Supabase and verified by row counts
- Temporary `anon` import access was removed after migration
- iOS shell now loads the overview screen live from the local backend instead of only from the bundled snapshot
- Backend repositories now read/write these domains from Supabase:
  - Customers
  - Order history
  - Quote history
  - Working orders
  - Delivery confirmations and delivery contacts
  - Project managers
  - Marketing pipeline, history, reminders, work managers, construction companies
  - Finance invoices, customer withholdings, bank movements
  - HR employees, payroll, contributions, hours, documents, payslip prep history

### Remaining work

- Move the remaining non-migrated domains from Sheets/JSON to Supabase-backed repositories:
  - Payments transfer snapshots and row-level payment mutations
  - Pazomat
  - Sibus
  - Finance settings
  - Inventory-related sheets
- Add authenticated internal mobile access for live operational data beyond the overview
- Route safe mobile write actions through backend endpoints backed by Supabase
