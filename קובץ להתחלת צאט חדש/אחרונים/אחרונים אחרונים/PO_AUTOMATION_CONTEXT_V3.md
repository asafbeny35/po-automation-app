# PO Automation App – FULL CONTEXT (V3)

## FLOW
PDF → Parse → Edit → Invoice → Label → Merge → WhatsApp → Sheets

## PROCESS
- extract text
- detect parser
- Plasan hard route supported
- return JSON

## FINALIZE
- create delivery + invoice
- generate label
- merge
- send WhatsApp
- append sheets

## PLASAN
- detect by Square meter + SKU
- sum quantities
- extract unit price
- calculate VAT
- fixed address
- fallback contact: קניין

## GOOGLE SHEETS
- requires spreadsheet_id
- requires service account
- writes A:M row

## STATUS
system stable and production ready
