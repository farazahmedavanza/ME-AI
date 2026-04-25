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
