-- Per-endpoint alert email for SLA / downtime notifications (empty → backend uses DEFAULT_MONITOR_ALERT_EMAIL)
alter table public.monitored_endpoints
  add column alert_email text;
