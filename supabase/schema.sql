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
