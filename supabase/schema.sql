-- API Health & SLA Monitor — run in Supabase SQL Editor
-- After creating a project, paste this, then enable RLS policies below.

create table if not exists upload_sessions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  filename text not null,
  uploaded_at timestamptz default now(),
  log_count integer,
  status text default 'processing'
);

create table if not exists api_logs (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references upload_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  log_timestamp timestamptz,
  endpoint text,
  method text,
  status_code integer,
  response_time_ms real,
  error_message text,
  service text,
  trace_id text,
  raw_json text
);

create table if not exists analysis_results (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references upload_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz default now(),
  health_summary jsonb,
  sla_status jsonb,
  incident_reports jsonb
);

create table if not exists alerts (
  id uuid primary key default gen_random_uuid(),
  session_id uuid not null references upload_sessions(id) on delete cascade,
  user_id uuid not null references auth.users(id) on delete cascade,
  created_at timestamptz default now(),
  endpoint text,
  severity text,
  description text,
  resolution_status text default 'open',
  resolved_at timestamptz,
  assignee text,
  title text
);

create index if not exists idx_api_logs_session on api_logs(session_id);
create index if not exists idx_alerts_session on alerts(session_id);

-- HTTP endpoint configuration & live monitor (CRUD via /api/endpoint-monitors; backend uses service role)
create table if not exists monitored_endpoints (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  name text not null,
  url text not null,
  method text default 'GET',
  expected_status_min integer default 200,
  expected_status_max integer default 299,
  timeout_ms integer default 10000,
  enabled boolean default true,
  sla_max_latency_ms integer default 3000,
  sla_min_uptime_pct real default 99.0,
  failure_threshold integer default 2,
  webhook_url text
);

create table if not exists endpoint_check_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  endpoint_id uuid not null references monitored_endpoints (id) on delete cascade,
  ok boolean not null,
  status_code integer,
  latency_ms real,
  error text,
  checked_at timestamptz not null
);

create table if not exists endpoint_monitor_state (
  user_id uuid not null references auth.users (id) on delete cascade,
  endpoint_id uuid not null references monitored_endpoints (id) on delete cascade,
  last_ok integer,
  consecutive_failures integer default 0,
  last_status_code integer,
  last_latency_ms real,
  last_checked_at timestamptz,
  last_error text,
  primary key (user_id, endpoint_id)
);

create table if not exists endpoint_monitor_alerts (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  endpoint_id uuid not null references monitored_endpoints (id) on delete cascade,
  name text,
  severity text,
  title text,
  description text,
  kind text,
  created_at timestamptz default now(),
  resolution_status text default 'open',
  resolved_at timestamptz
);

create index if not exists idx_ech_user_ep on endpoint_check_history (user_id, endpoint_id, checked_at);
create index if not exists idx_ema_user on endpoint_monitor_alerts (user_id, created_at);

-- Row Level Security
alter table upload_sessions enable row level security;
alter table api_logs enable row level security;
alter table analysis_results enable row level security;
alter table alerts enable row level security;

create policy "Users own upload_sessions" on upload_sessions
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users own api_logs" on api_logs
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users own analysis_results" on analysis_results
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users own alerts" on alerts
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);

alter table monitored_endpoints enable row level security;
alter table endpoint_check_history enable row level security;
alter table endpoint_monitor_state enable row level security;
alter table endpoint_monitor_alerts enable row level security;

create policy "Users own monitored_endpoints" on monitored_endpoints
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users own endpoint_check_history" on endpoint_check_history
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users own endpoint_monitor_state" on endpoint_monitor_state
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "Users own endpoint_monitor_alerts" on endpoint_monitor_alerts
  for all using (auth.uid() = user_id) with check (auth.uid() = user_id);
