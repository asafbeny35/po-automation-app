# PO Automation App – FULL CONTEXT (UPDATED)

## Overview
Automated Purchase Order processing system:
PDF → Parse → Edit → Green Invoice → Label → Merge → WhatsApp → Google Sheets

---

## Current Working Flow

### /process
- Upload PDF
- Extract text
- Parse via registry + fallback
- Enrich with GreenInvoice (existing customer only)
- Preserve original PDF fields:
  - delivery_address
  - contact_name
  - contact_phone
- Return data to frontend

---

### /finalize
- Receive edited data
- Create delivery note + invoice (GreenInvoice)
- Generate label PDF
- Save files in folder
- Merge PDFs
- Send via WhatsApp (single file)
- Update Google Sheets

---

## Output Files

Folder:
output/{customer} - {po_number}/

Contains:
- delivery.pdf
- invoice.pdf
- label.pdf
- original PO
- merged.pdf

---

## Merged PDF Rules (CRITICAL)

Must contain:
1. Delivery note
2. Delivery note (duplicate)
3. Label

Must NOT contain:
- Invoice
- PO

---

## WhatsApp

- Sends ONE file only (merged.pdf)
- Locked phone:
0547720142

---

## Data Model

PurchaseOrderData.extra:

{
  "project": "",
  "delivery_address": "",
  "contact_name": "",
  "contact_phone": "",
  "footer_text": ""
}

---

## Known Issues (CURRENT)

### 1. Data Loss (CRITICAL)
delivery_address / contact_phone sometimes lost between process → finalize

Fix approach:
Preserve before GI merge and restore after.

---

### 2. Label Missing Data
Label sometimes empty because:
po.delivery_address is empty

Fix:
Use fallback:
po.delivery_address or po.extra["delivery_address"]

---

### 3. Google Sheets Not Updating
Cause:
Missing credentials file / env vars

Required ENV:
GOOGLE_SERVICE_ACCOUNT_JSON
GOOGLE_SHEETS_SPREADSHEET_ID
GOOGLE_SHEETS_RANGE

---

### 4. Playwright (Label Generator)

Uses sync API inside async:
sync_playwright()

Status:
Works but fragile

---

## Working Components (Verified)

- GreenInvoice ✅
- Label generation ✅
- PDF merge ✅
- WhatsApp (single file) ✅

---

## System Rules

- Do NOT create new customers
- Always use existing customer_id
- Always trust PDF for:
  - delivery_address
  - contact details
- Do NOT overwrite extracted data

---

## Important Files

- app.py → main flow
- services/greeninvoice.py
- services/label_generator_v4.py
- services/whatsapp_web.py
- services/google_sheets.py

---

## Development Rules

- No refactoring
- No breaking changes
- Only minimal fixes
- Stability over improvements

---

## Status

System is near production.
Remaining issues:
- Data consistency
- Google Sheets integration
- Playwright stability
