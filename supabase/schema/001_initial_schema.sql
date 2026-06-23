create extension if not exists pgcrypto;

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = timezone('utc', now());
  return new;
end;
$$;

create table if not exists public.internal_users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text,
  role text not null default 'staff',
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create or replace function public.is_internal_user()
returns boolean
language sql
stable
as $$
  select exists (
    select 1
    from public.internal_users iu
    where iu.user_id = auth.uid()
  );
$$;

create table if not exists public.customers (
  id text primary key,
  customer_guid text unique,
  customer_name text not null,
  customer_id text,
  source_mode text,
  active boolean default true,
  send boolean,
  department text,
  accounting_key text,
  payment_terms_days integer,
  phone text,
  mobile text,
  emails jsonb not null default '[]'::jsonb,
  contact_person text,
  address text,
  city text,
  zip text,
  country text,
  bank_name text,
  bank_branch text,
  bank_account text,
  remarks text,
  income_amount numeric(14,2),
  payment_amount numeric(14,2),
  balance_amount numeric(14,2),
  creation_date text,
  last_update_date text,
  customer_domain text,
  bank_details_updated_sent boolean default false,
  synced_at timestamptz,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.order_history (
  id text primary key,
  history_id text unique,
  created_at_source text,
  input_source text,
  mode text,
  customer_name text,
  customer_id text,
  customer_email text,
  customer_phone text,
  delivery_address text,
  project text,
  contact_name text,
  contact_phone text,
  payment_terms_days integer,
  payment_terms_label text,
  po_number text,
  quote_number text,
  fulfillment_id text,
  document_mode text,
  order_status_tag text,
  delivery_document_number text,
  delivery_document_id text,
  tax_invoice_number text,
  tax_invoice_document_id text,
  item_description text,
  item_sku text,
  item_unit text,
  item_quantity numeric(14,2),
  item_unit_price numeric(14,2),
  item_line_total numeric(14,2),
  subtotal numeric(14,2),
  vat numeric(14,2),
  total numeric(14,2),
  footer_text text,
  items_json jsonb,
  label_split_rows_json jsonb,
  document_links_json jsonb,
  drive_payload jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.quote_history (
  id text primary key,
  history_id text unique,
  created_at_source text,
  input_source text,
  mode text,
  customer_name text,
  customer_id text,
  po_number text,
  quote_number text,
  quote_document_id text,
  quote_date text,
  customer_email text,
  customer_phone text,
  delivery_address text,
  project text,
  contact_name text,
  contact_phone text,
  payment_terms_days integer,
  payment_terms_label text,
  item_description text,
  item_sku text,
  item_unit text,
  item_quantity numeric(14,2),
  item_unit_price numeric(14,2),
  item_line_total numeric(14,2),
  subtotal numeric(14,2),
  vat numeric(14,2),
  total numeric(14,2),
  footer_text text,
  items_json jsonb,
  label_split_rows_json jsonb,
  quote_mail_status text,
  quote_mail_sent_at text,
  document_links_json jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.working_orders (
  id text primary key,
  row_id text unique,
  created_at_source text,
  updated_at_source text,
  source_file_name text,
  source_file_path text,
  po_date text,
  customer_name text,
  customer_id text,
  customer_email text,
  customer_phone text,
  delivery_address text,
  project text,
  contact_name text,
  contact_phone text,
  payment_terms_days integer,
  payment_terms_label text,
  po_number text,
  item_description text,
  item_sku text,
  item_unit text,
  item_quantity numeric(14,2),
  item_unit_price numeric(14,2),
  subtotal numeric(14,2),
  vat numeric(14,2),
  total numeric(14,2),
  items_count integer,
  items_json jsonb,
  payload_json jsonb,
  drive_payload jsonb,
  order_note_text text,
  order_note_file_name text,
  order_note_file_path text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.delivery_confirmations (
  id text primary key,
  history_id text,
  order_date text,
  company text,
  po_number text,
  invoice_date text,
  tax_invoice_number text,
  order_total numeric(14,2),
  target_email text,
  signed_delivery_name text,
  signed_delivery_local_path text,
  invoice_drive_file_id text,
  coc_name text,
  coc_drive_file_id text,
  order_drive_folder_id text,
  order_drive_folder_url text,
  fulfillment_id text,
  document_mode text,
  delivery_document_number text,
  delivery_document_id text,
  sent boolean default false,
  sent_at text,
  updated_at_source text,
  source_mode text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.delivery_contacts (
  id text primary key,
  company text,
  customer_id text,
  accounting_email text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.project_managers (
  id text primary key,
  company text,
  tax_id text,
  site_address text,
  contact_name text,
  order_date text,
  item text,
  contact_phone text,
  history_dates text,
  editable_company text,
  editable_tax_id text,
  editable_site_address text,
  editable_contact_name text,
  editable_order_date text,
  editable_item text,
  editable_contact_phone text,
  source_key text,
  updated_at_source text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.marketing_pipeline (
  id text primary key,
  customer_key text,
  customer_guid text,
  customer_id text,
  customer_name text,
  quote_number text,
  quote_document_id text,
  quote_date text,
  item_name text,
  emails jsonb not null default '[]'::jsonb,
  phone text,
  contact_name text,
  note_text text,
  comm_status text,
  comm_sent_at text,
  mail_subject text,
  mail_sent_at text,
  quote_drive_url text,
  quote_drive_file_id text,
  quote_source_url text,
  source text,
  updated_at_source text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.marketing_history (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.marketing_reminders (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.marketing_work_managers (
  id text primary key,
  row_id text,
  full_name text,
  company_name text,
  email text,
  phone_1 text,
  phone_2 text,
  phone_3 text,
  active_status text,
  current_employer text,
  current_workplace text,
  details_url text,
  project_manager_match text,
  project_manager_checked_at text,
  updated_at_source text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.marketing_construction_companies (
  id text primary key,
  row_id text,
  company_name text,
  company_id text,
  phone text,
  address text,
  email text,
  details_url text,
  notes text,
  updated_at_source text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.finance_invoices (
  id text primary key,
  row_id text unique,
  invoice_date text,
  supplier_name text,
  reference_number text,
  allocation_number text,
  currency_code text,
  service_or_product text,
  subtotal numeric(14,2),
  vat numeric(14,2),
  total numeric(14,2),
  source_file_name text,
  source_file_path text,
  report_due_date text,
  report_due_overrides jsonb,
  drive_file_id text,
  drive_url text,
  updated_at_source text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.finance_customer_withholdings (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.finance_bank_movements (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.payments_transfer_snapshots (
  id text primary key,
  current_sheet text,
  sheet_names jsonb,
  recent_rows jsonb,
  historical_rows jsonb,
  all_rows jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.pazomat (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.sibus (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.supplier_delivery_notes (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.inventory_purchase_orders (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.pricing_items (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.pricing_components (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.inventory_raw (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.inventory_finish (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.inventory_contacts (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.hr_employees (
  id text primary key,
  employee_id text unique,
  full_name text,
  id_number text,
  employment_type text,
  active_status text,
  start_date text,
  base_salary numeric(14,2),
  hourly_rate numeric(14,2),
  phone text,
  email text,
  pension_fund text,
  notes text,
  drive_folder_id text,
  drive_folder_url text,
  updated_at_source text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.hr_hours (
  id text primary key,
  row_id text unique,
  employee_id text,
  employee_name text,
  month_key text,
  regular_hours numeric(14,2),
  overtime_hours numeric(14,2),
  hourly_rate numeric(14,2),
  status text,
  hours_file_name text,
  hours_drive_file_id text,
  hours_drive_url text,
  updated_at_source text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.hr_payroll (
  id text primary key,
  row_id text unique,
  employee_id text,
  employee_name text,
  month_key text,
  employment_type text,
  gross_amount numeric(14,2),
  net_amount numeric(14,2),
  salary_paid text,
  salary_paid_date text,
  salary_reference text,
  payslip_file_name text,
  payslip_drive_file_id text,
  payslip_drive_url text,
  updated_at_source text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.hr_contributions (
  id text primary key,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.hr_documents (
  id text primary key,
  row_id text unique,
  employee_id text,
  employee_name text,
  category text,
  title text,
  month_key text,
  file_name text,
  drive_file_id text,
  drive_url text,
  updated_at_source text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.hr_payslip_prep_history (
  id text primary key,
  row_id text unique,
  month_key text,
  month_label text,
  send_mode text,
  sent_to text,
  sent_at text,
  employees_total integer,
  gross_total_label text,
  attachments_count integer,
  supporting_summaries_json jsonb,
  notes text,
  updated_at_source text,
  raw_payload jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

create table if not exists public.app_settings (
  key text primary key,
  value jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default timezone('utc', now()),
  updated_at timestamptz not null default timezone('utc', now())
);

do $$
declare
  table_name text;
begin
  for table_name in
    select unnest(array[
      'internal_users',
      'customers',
      'order_history',
      'quote_history',
      'working_orders',
      'delivery_confirmations',
      'delivery_contacts',
      'project_managers',
      'marketing_pipeline',
      'marketing_history',
      'marketing_reminders',
      'marketing_work_managers',
      'marketing_construction_companies',
      'finance_invoices',
      'finance_customer_withholdings',
      'finance_bank_movements',
      'payments_transfer_snapshots',
      'pazomat',
      'sibus',
      'supplier_delivery_notes',
      'inventory_purchase_orders',
      'pricing_items',
      'pricing_components',
      'inventory_raw',
      'inventory_finish',
      'inventory_contacts',
      'hr_employees',
      'hr_hours',
      'hr_payroll',
      'hr_contributions',
      'hr_documents',
      'hr_payslip_prep_history',
      'app_settings'
    ])
  loop
    execute format('alter table public.%I enable row level security', table_name);
    execute format('drop trigger if exists touch_updated_at on public.%I', table_name);
    execute format(
      'create trigger touch_updated_at before update on public.%I for each row execute function public.touch_updated_at()',
      table_name
    );
  end loop;
end;
$$;

grant usage on schema public to authenticated;

grant select, insert, update, delete
on table
  public.internal_users,
  public.customers,
  public.order_history,
  public.quote_history,
  public.working_orders,
  public.delivery_confirmations,
  public.delivery_contacts,
  public.project_managers,
  public.marketing_pipeline,
  public.marketing_history,
  public.marketing_reminders,
  public.marketing_work_managers,
  public.marketing_construction_companies,
  public.finance_invoices,
  public.finance_customer_withholdings,
  public.finance_bank_movements,
  public.payments_transfer_snapshots,
  public.pazomat,
  public.sibus,
  public.supplier_delivery_notes,
  public.inventory_purchase_orders,
  public.pricing_items,
  public.pricing_components,
  public.inventory_raw,
  public.inventory_finish,
  public.inventory_contacts,
  public.hr_employees,
  public.hr_hours,
  public.hr_payroll,
  public.hr_contributions,
  public.hr_documents,
  public.hr_payslip_prep_history,
  public.app_settings
to authenticated;

do $$
declare
  table_name text;
begin
  for table_name in
    select unnest(array[
      'internal_users',
      'customers',
      'order_history',
      'quote_history',
      'working_orders',
      'delivery_confirmations',
      'delivery_contacts',
      'project_managers',
      'marketing_pipeline',
      'marketing_history',
      'marketing_reminders',
      'marketing_work_managers',
      'marketing_construction_companies',
      'finance_invoices',
      'finance_customer_withholdings',
      'finance_bank_movements',
      'payments_transfer_snapshots',
      'pazomat',
      'sibus',
      'supplier_delivery_notes',
      'inventory_purchase_orders',
      'pricing_items',
      'pricing_components',
      'inventory_raw',
      'inventory_finish',
      'inventory_contacts',
      'hr_employees',
      'hr_hours',
      'hr_payroll',
      'hr_contributions',
      'hr_documents',
      'hr_payslip_prep_history',
      'app_settings'
    ])
  loop
    execute format('drop policy if exists internal_select on public.%I', table_name);
    execute format('drop policy if exists internal_insert on public.%I', table_name);
    execute format('drop policy if exists internal_update on public.%I', table_name);
    execute format('drop policy if exists internal_delete on public.%I', table_name);

    execute format(
      'create policy internal_select on public.%I for select to authenticated using (public.is_internal_user())',
      table_name
    );
    execute format(
      'create policy internal_insert on public.%I for insert to authenticated with check (public.is_internal_user())',
      table_name
    );
    execute format(
      'create policy internal_update on public.%I for update to authenticated using (public.is_internal_user()) with check (public.is_internal_user())',
      table_name
    );
    execute format(
      'create policy internal_delete on public.%I for delete to authenticated using (public.is_internal_user())',
      table_name
    );
  end loop;
end;
$$;
