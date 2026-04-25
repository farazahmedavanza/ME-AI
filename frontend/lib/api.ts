const API_BASE =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL) ||
  "http://127.0.0.1:8000";

const TOKEN_KEY = "avanza_ops_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(t: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, t);
}

export async function fetchToken() {
  const r = await fetch(`${API_BASE}/api/auth/token`, { method: "POST" });
  if (!r.ok) throw new Error("Could not get token");
  const d = (await r.json()) as { access_token: string };
  setToken(d.access_token);
  return d.access_token;
}

export async function apiGet(path: string) {
  let tok = getToken();
  if (!tok) tok = await fetchToken();
  const r = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${tok}` },
    cache: "no-store",
  });
  if (r.status === 401) {
    tok = await fetchToken();
    return fetch(`${API_BASE}${path}`, {
      headers: { Authorization: `Bearer ${tok}` },
      cache: "no-store",
    }).then((x) => x);
  }
  return r;
}

export async function apiPost(path: string, body: unknown) {
  let tok = getToken();
  if (!tok) tok = await fetchToken();
  return fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${tok}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export async function apiPatch(path: string, body: unknown) {
  let tok = getToken();
  if (!tok) tok = await fetchToken();
  return fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${tok}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });
}

export function apiBase() {
  return API_BASE;
}

export type HealthInfo = {
  store: string;
  ai: string;
  version: string;
  app_name?: string;
  store_fallback?: boolean;
};

export async function getHealth() {
  const r = await fetch(`${API_BASE}/api/health`, { cache: "no-store" });
  return r.json() as Promise<HealthInfo>;
}

export type MonitorSla = {
  breached: boolean | null;
  latency_ok: boolean | null;
  uptime_ok: boolean | null;
  max_latency_ms?: number;
  min_uptime_pct?: number;
};

export type MonitoredEndpointView = {
  id: string;
  name: string;
  url: string;
  method: string;
  enabled: boolean;
  last_check: {
    ok: boolean;
    status_code: number | null;
    latency_ms: number;
    error?: string | null;
    checked_at: string;
  } | null;
  consecutive_failures: number;
  uptime_24h_pct: number | null;
  sla: MonitorSla;
  sparkline: number[];
  config?: {
    sla_max_latency_ms: number;
    sla_min_uptime_pct: number;
    failure_threshold: number;
  };
};

export type EndpointMonitorAlert = {
  id: string;
  endpoint_id: string;
  name: string | null;
  severity: string;
  title: string | null;
  description: string | null;
  kind: string | null;
  created_at: string;
  resolution_status: string;
  resolved_at: string | null;
};

export type EndpointMonitorsResponse = {
  ok: boolean;
  endpoints: MonitoredEndpointView[];
  alerts: EndpointMonitorAlert[];
  checked_at?: string;
  error?: string;
};

export async function getEndpointMonitors(refresh = true) {
  const r = await apiGet(
    `/api/endpoint-monitors?refresh=${refresh ? "true" : "false"}`,
  );
  if (!r.ok) {
    const t = await r.text();
    throw new Error(t || r.statusText);
  }
  return r.json() as Promise<EndpointMonitorsResponse>;
}

export async function patchMonitoredEndpoint(
  id: string,
  body: Record<string, unknown>,
) {
  return apiPatch(`/api/endpoint-monitors/${id}`, body);
}

export async function patchEndpointMonitorAlert(id: string) {
  return apiPatch(`/api/endpoint-monitors/monitor-alerts/${id}`, {
    resolution_status: "resolved",
  });
}
