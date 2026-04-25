"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { AlertCircle, CheckCircle2, Filter, Radio, XCircle } from "lucide-react";
import { cn } from "@/lib/cn";
import { ToastBar } from "@/components/toast-bar";
import {
  getEndpointMonitors,
  patchEndpointMonitorAlert,
  type EndpointMonitorsResponse,
} from "@/lib/api";

const POLL_MS = 45_000;

type FilterKey = "all" | "up" | "down" | "breach";

function Sparkline({ values }: { values: number[] }) {
  if (!values.length) {
    return <span className="text-xs text-slate-500">—</span>;
  }
  return (
    <div className="flex items-end gap-0.5" title="Last 12 checks (left→right)">
      {values.map((v, i) => (
        <div
          key={i}
          className={cn(
            "w-1.5 rounded-sm",
            v === 1 ? "h-3 bg-emerald-600" : "h-1.5 bg-rose-600",
          )}
        />
      ))}
    </div>
  );
}

export function ConfigureEndpointsClient() {
  const [data, setData] = useState<EndpointMonitorsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<{
    msg: string;
    kind: "error" | "success" | "info";
  } | null>(null);
  const seenAlertIds = useRef<Set<string>>(new Set());
  const initialAlerts = useRef(true);

  const load = useCallback(async (refresh: boolean) => {
    setError(null);
    if (refresh) setBusy(true);
    try {
      const r = await getEndpointMonitors(refresh);
      if (!r.ok && r.error) {
        setError(r.error);
        return;
      }
      setData(r);
      if (initialAlerts.current) {
        (r.alerts || []).forEach((a) => seenAlertIds.current.add(a.id));
        initialAlerts.current = false;
      } else {
        for (const a of r.alerts || []) {
          if (a.resolution_status !== "open") continue;
          if (!seenAlertIds.current.has(a.id)) {
            seenAlertIds.current.add(a.id);
            setToast({
              kind: a.severity === "critical" ? "error" : "info",
              msg: a.title || a.description || "New monitor alert",
            });
            break;
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load monitors");
    } finally {
      if (refresh) setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load(true);
  }, [load]);

  useEffect(() => {
    const t = setInterval(() => void load(true), POLL_MS);
    return () => clearInterval(t);
  }, [load]);

  const filtered = (data?.endpoints || []).filter((e) => {
    const lc = e.last_check;
    const up = lc ? lc.ok : null;
    const br = e.sla?.breached;
    if (filter === "up") return up === true;
    if (filter === "down") return up === false;
    if (filter === "breach") return br === true;
    return true;
  });

  async function resolve(alertId: string) {
    setBusy(true);
    try {
      const r = await patchEndpointMonitorAlert(alertId);
      if (!r.ok) {
        const t = await r.text();
        setToast({ kind: "error", msg: t || "Could not resolve alert" });
        return;
      }
      setToast({ kind: "success", msg: "Alert marked resolved" });
      await load(true);
    } catch (e) {
      setToast({
        kind: "error",
        msg: e instanceof Error ? e.message : "Request failed",
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-light tracking-tight text-white">
          Configure endpoints
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-400">
          Live HTTP checks run on the server (no browser CORS). The row{" "}
          <span className="text-rose-300">Simulated outage (httpstat 503)</span>{" "}
          calls{" "}
          <code className="rounded bg-slate-800 px-1">https://httpstat.us/503</code> — it
          always returns 503, so the UI shows a down / SLA-breached state.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Filter className="h-4 w-4 text-slate-500" aria-hidden />
        {(
          [
            ["all", "All"],
            ["up", "Up"],
            ["down", "Down"],
            ["breach", "SLA breach"],
          ] as const
        ).map(([k, label]) => (
          <button
            key={k}
            type="button"
            onClick={() => setFilter(k)}
            className={cn(
              "rounded border px-2 py-1 text-xs",
              filter === k
                ? "border-blue-500 bg-blue-950/50 text-blue-200"
                : "border-avline bg-slate-900/50 text-slate-400 hover:border-slate-600",
            )}
          >
            {label}
          </button>
        ))}
        <div className="ml-auto flex items-center gap-2 text-xs text-slate-500">
          <Radio
            className={cn("h-4 w-4", busy && "animate-pulse text-blue-400")}
            aria-hidden
          />
          {data?.checked_at
            ? `Last run ${new Date(data.checked_at).toLocaleTimeString()}`
            : "—"}
          <span className="text-slate-600">· poll {POLL_MS / 1000}s</span>
        </div>
      </div>

      {error && (
        <div className="rounded border border-rose-800 bg-rose-950/40 px-3 py-2 text-sm text-rose-100">
          {error}
        </div>
      )}

      {toast && (
        <ToastBar
          message={toast.msg}
          kind={toast.kind}
          onClose={() => setToast(null)}
        />
      )}

      <div className="overflow-x-auto rounded border border-avline bg-slate-950/40">
        <table className="w-full min-w-[900px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-avline text-xs uppercase text-slate-500">
              <th className="px-3 py-2 font-medium">Name</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Code</th>
              <th className="px-3 py-2 font-medium">Latency</th>
              <th className="px-3 py-2 font-medium">24h up %</th>
              <th className="px-3 py-2 font-medium">SLA</th>
              <th className="px-3 py-2 font-medium">Last check</th>
              <th className="px-3 py-2 font-medium">History</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((e) => {
              const lc = e.last_check;
              const st = e.enabled
                ? lc?.ok
                  ? "up"
                  : "down"
                : "off";
              return (
                <tr
                  key={e.id}
                  className="border-b border-avline/60 hover:bg-slate-900/40"
                >
                  <td className="px-3 py-2 align-top">
                    <div className="font-medium text-slate-200">{e.name}</div>
                    <div
                      className="mt-0.5 max-w-[32rem] truncate text-xs text-slate-500"
                      title={e.url}
                    >
                      {e.url}
                    </div>
                  </td>
                  <td className="px-3 py-2">
                    {st === "off" && (
                      <span className="text-xs text-slate-500">Disabled</span>
                    )}
                    {st === "up" && (
                      <span className="inline-flex items-center gap-1 text-emerald-400">
                        <CheckCircle2 className="h-4 w-4" />
                        Up
                      </span>
                    )}
                    {st === "down" && (
                      <span className="inline-flex items-center gap-1 text-rose-400">
                        <XCircle className="h-4 w-4" />
                        Down
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-slate-300">
                    {lc?.status_code ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-slate-300">
                    {lc != null
                      ? `${Number(lc.latency_ms).toFixed(0)} ms`
                      : "—"}
                  </td>
                  <td className="px-3 py-2 text-slate-300">
                    {e.uptime_24h_pct != null
                      ? `${e.uptime_24h_pct.toFixed(1)}%`
                      : "—"}
                  </td>
                  <td className="px-3 py-2">
                    {e.sla?.breached === true && (
                      <span className="text-xs font-medium text-amber-300">
                        Breach
                      </span>
                    )}
                    {e.sla?.breached === false && (
                      <span className="text-xs text-emerald-500/90">OK</span>
                    )}
                    {e.sla?.breached == null && (
                      <span className="text-xs text-slate-500">—</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-500">
                    {lc?.checked_at
                      ? new Date(lc.checked_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="px-3 py-2">
                    <Sparkline values={e.sparkline || []} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {filtered.length === 0 && (
          <p className="p-4 text-sm text-slate-500">No rows match this filter.</p>
        )}
      </div>

      <div>
        <h2 className="text-lg font-medium text-slate-200">Endpoint alerts</h2>
        <p className="mb-2 text-xs text-slate-500">
          Alerts fire when an endpoint goes from up to down (critical), or after N
          consecutive failures when no open alert exists. Resolve to clear.
        </p>
        <ul className="space-y-2">
          {(data?.alerts || [])
            .filter((a) => a.resolution_status === "open")
            .map((a) => (
              <li
                key={a.id}
                className="flex flex-wrap items-start gap-2 rounded border border-avline bg-slate-900/30 px-3 py-2 text-sm"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-slate-200">{a.title}</div>
                  <div className="text-xs text-slate-500">{a.description}</div>
                  <div className="mt-1 text-[10px] uppercase text-slate-600">
                    {a.severity} · {a.kind}
                  </div>
                </div>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void resolve(a.id)}
                  className="shrink-0 rounded border border-avline px-2 py-1 text-xs text-slate-300 hover:border-slate-500 hover:bg-slate-800 disabled:opacity-50"
                >
                  Resolve
                </button>
              </li>
            ))}
          {!(data?.alerts || []).some((a) => a.resolution_status === "open") && (
            <li className="text-sm text-slate-500">No open alerts.</li>
          )}
        </ul>
      </div>
    </div>
  );
}
