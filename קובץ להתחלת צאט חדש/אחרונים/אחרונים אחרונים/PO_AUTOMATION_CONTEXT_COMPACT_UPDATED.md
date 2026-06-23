# PO Automation – AI CONTEXT (COMPACT UPDATED)

## FLOW
PDF → /process → JSON → /finalize → Docs → Label → Merge → WhatsApp → Sheets → Transport

## MODES
sandbox → extract only  
prod → create docs  
sandbox_with_transport → sandbox + transport  
prod_with_transport → prod + transport  

run_transport = mode in ("prod_with_transport","sandbox_with_transport")

## /process
- parse PDF (multi-parser system)
- includes Plasan HARD ROUTE detection
- returns JSON ONLY
❌ no docs

## /finalize
- delivery + invoice
- label
- merge PDFs
- WhatsApp
- Google Sheets

## PLASAN SUPPORT
- merged quantities
- VAT auto (18%)
- fixed address
- label override SKU 5430000030-00 → סקאי אפור חורים
- unit: מ"ר

## GOOGLE SHEETS
requires:
GOOGLE_SHEETS_SPREADSHEET_ID  
GOOGLE_SERVICE_ACCOUNT_JSON  

writes row after finalize

## STATUS
✔ fully working
✔ stable
