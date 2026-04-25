"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Filter,
  Pencil,
  Radio,
  Trash2,
  XCircle,
} from "lucide-react";
import { cn } from "@/lib/cn";
import { ToastBar } from "@/components/toast-bar";
import {
  deleteMonitoredEndpoint,
  getEndpointMonitors,
  patchEndpointMonitorAlert,
  patchMonitoredEndpoint,
  postMonitoredEndpoint,
  type EndpointMonitorsResponse,
  type MonitorEndpointWriteBody,
  type MonitoredEndpointView,
} from "@/lib/api";

const POLL_MS = 45_000;

type FilterKey = "all" | "up" | "down" | "breach";

const emptyForm: MonitorEndpointWriteBody = {
  name: "",
  url: "",
  method: "GET",
  expected_status_min: 200,
  expected_status_max: 299,
  timeout_ms: 10_000,
  enabled: true,
  sla_max_latency_ms: 3000,
  sla_min_uptime_pct: 99,
  failure_threshold: 2,
  webhook_url: "",
};

function viewToForm(e: MonitoredEndpointView): MonitorEndpointWriteBody {
  return {
    name: e.name,
    url: e.url,
    method: e.method || "GET",
    expected_status_min: e.expected_status_min ?? 200,
    expected_status_max: e.expected_status_max ?? 299,
    timeout_ms: e.timeout_ms ?? 10_000,
    enabled: e.enabled,
    sla_max_latency_ms: e.config?.sla_max_latency_ms ?? 3000,
    sla_min_uptime_pct: e.config?.sla_min_uptime_pct ?? 99,
    failure_threshold: e.config?.failure_threshold ?? 2,
    webhook_url: e.webhook_url ?? "",
  };
}

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

function EndpointFormFields({
  value,
  onChange,
  idPrefix,
}: {
  value: MonitorEndpointWriteBody;
  onChange: (v: MonitorEndpointWriteBody) => void;
  idPrefix: string;
}) {
  const set = (patch: Partial<MonitorEndpointWriteBody>) =>
    onChange({ ...value, ...patch });

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <label className="block text-xs text-slate-400">
        Name
        <input
          id={`${idPrefix}-name`}
          className="mt-1 w-full rounded border border-avline bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          value={value.name}
          onChange={(e) => set({ name: e.target.value })}
          required
        />
      </label>
      <label className="block text-xs text-slate-400 sm:col-span-2">
        URL
        <input
          id={`${idPrefix}-url`}
          className="mt-1 w-full rounded border border-avline bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          value={value.url}
          onChange={(e) => set({ url: e.target.value })}
          required
        />
      </label>
      <label className="block text-xs text-slate-400">
        Method
        <select
          id={`${idPrefix}-method`}
          className="mt-1 w-full rounded border border-avline bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          value={value.method || "GET"}
          onChange={(e) => set({ method: e.target.value })}
        >
          {["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"].map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </label>
      <label className="block text-xs text-slate-400">
        Expected status min
        <input
          type="number"
          id={`${idPrefix}-min`}
          className="mt-1 w-full rounded border border-avline bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          value={value.expected_status_min ?? 200}
          onChange={(e) =>
            set({ expected_status_min: Number.parseInt(e.target.value, 10) || 0 })
          }
        />
      </label>
      <label className="block text-xs text-slate-400">
        Expected status max
        <input
          type="number"
          id={`${idPrefix}-max`}
          className="mt-1 w-full rounded border border-avline bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          value={value.expected_status_max ?? 299}
          onChange={(e) =>
            set({ expected_status_max: Number.parseInt(e.target.value, 10) || 0 })
          }
        />
      </label>
      <label className="block text-xs text-slate-400">
        Timeout (ms)
        <input
          type="number"
          id={`${idPrefix}-timeout`}
          className="mt-1 w-full rounded border border-avline bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          value={value.timeout_ms ?? 10_000}
          onChange={(e) =>
            set({ timeout_ms: Number.parseInt(e.target.value, 10) || 0 })
          }
        />
      </label>
      <label className="block text-xs text-slate-400">
        SLA max latency (ms)
        <input
          type="number"
          id={`${idPrefix}-sla-lat`}
          className="mt-1 w-full rounded border border-avline bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          value={value.sla_max_latency_ms ?? 3000}
          onChange={(e) =>
            set({ sla_max_latency_ms: Number.parseInt(e.target.value, 10) || 0 })
          }
        />
      </label>
      <label className="block text-xs text-slate-400">
        SLA min uptime %
        <input
          type="number"
          step="0.1"
          id={`${idPrefix}-sla-up`}
          className="mt-1 w-full rounded border border-avline bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          value={value.sla_min_uptime_pct ?? 99}
          onChange={(e) =>
            set({ sla_min_uptime_pct: Number.parseFloat(e.target.value) || 0 })
          }
        />
      </label>
      <label className="block text-xs text-slate-400">
        Failure threshold
        <input
          type="number"
          min={1}
          id={`${idPrefix}-thr`}
          className="mt-1 w-full rounded border border-avline bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          value={value.failure_threshold ?? 2}
          onChange={(e) =>
            set({ failure_threshold: Number.parseInt(e.target.value, 10) || 1 })
          }
        />
      </label>
      <label className="flex items-center gap-2 text-xs text-slate-400 sm:col-span-2">
        <input
          type="checkbox"
          id={`${idPrefix}-en`}
          checked={Boolean(value.enabled)}
          onChange={(e) => set({ enabled: e.target.checked })}
        />
        Enabled
      </label>
      <label className="block text-xs text-slate-400 sm:col-span-2 lg:col-span-3">
        Webhook URL (optional stub)
        <input
          id={`${idPrefix}-wh`}
          className="mt-1 w-full rounded border border-avline bg-slate-900 px-2 py-1.5 text-sm text-slate-100"
          value={value.webhook_url || ""}
          onChange={(e) =>
            set({ webhook_url: e.target.value.trim() || null })
          }
          placeholder="https://…"
        />
      </label>
    </div>
  );
}

export function LiveMonitoringClient() {
  const [data, setData] = useState<EndpointMonitorsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [busy, setBusy] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [createForm, setCreateForm] = useState<MonitorEndpointWriteBody>(emptyForm);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<MonitorEndpointWriteBody>(emptyForm);
  const [crudError, setCrudError] = useState<string | null>(null);
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

  function startEdit(e: MonitoredEndpointView) {
    setEditingId(e.id);
    setEditForm(viewToForm(e));
    setCrudError(null);
  }

  function cancelEdit() {
    setEditingId(null);
    setEditForm(emptyForm);
    setCrudError(null);
  }

  async function submitCreate(ev: React.FormEvent) {
    ev.preventDefault();
    setCrudError(null);
    setBusy(true);
    try {
      const body = {
        ...createForm,
        webhook_url: createForm.webhook_url || null,
      };
      const r = await postMonitoredEndpoint(body);
      if (!r.ok) {
        const t = await r.text();
        setCrudError(t || "Create failed");
        return;
      }
      setCreateForm(emptyForm);
      setToast({ kind: "success", msg: "Endpoint added" });
      await load(true);
    } catch (e) {
      setCrudError(e instanceof Error ? e.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function submitEdit(ev: React.FormEvent) {
    ev.preventDefault();
    if (!editingId) return;
    setCrudError(null);
    setBusy(true);
    try {
      const r = await patchMonitoredEndpoint(editingId, {
        ...editForm,
        webhook_url: editForm.webhook_url || null,
      });
      if (!r.ok) {
        const t = await r.text();
        setCrudError(t || "Update failed");
        return;
      }
      cancelEdit();
      setToast({ kind: "success", msg: "Endpoint updated" });
      await load(true);
    } catch (e) {
      setCrudError(e instanceof Error ? e.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function removeEndpoint(id: string, name: string) {
    if (
      !window.confirm(
        `Delete monitored endpoint “${name}”? History and alerts for this endpoint will be removed.`,
      )
    ) {
      return;
    }
    setCrudError(null);
    setBusy(true);
    try {
      const r = await deleteMonitoredEndpoint(id);
      if (!r.ok) {
        const t = await r.text();
        setCrudError(t || "Delete failed");
        return;
      }
      if (editingId === id) cancelEdit();
      setToast({ kind: "success", msg: "Endpoint deleted" });
      await load(true);
    } catch (e) {
      setCrudError(e instanceof Error ? e.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-light tracking-tight text-white">
          Live Monitoring
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-400">
          Live HTTP checks run on the server (no browser CORS). The row{" "}
          <span className="text-rose-300">Simulated outage (httpstat 503)</span>{" "}
          calls{" "}
          <code className="rounded bg-slate-800 px-1">https://httpstat.us/503</code> — it
          always returns 503, so the UI shows a down / SLA-breached state. Use{" "}
          <span className="text-slate-200">Configure endpoints</span> below to add or
          edit monitors.
        </p>
      </div>

      <div className="rounded border border-avline bg-slate-950/40">
        <button
          type="button"
          onClick={() => setConfigOpen((o) => !o)}
          className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm font-medium text-slate-200 hover:bg-slate-900/50"
        >
          {configOpen ? (
            <ChevronDown className="h-4 w-4 shrink-0 text-slate-500" />
          ) : (
            <ChevronRight className="h-4 w-4 shrink-0 text-slate-500" />
          )}
          Configure endpoints
          <span className="ml-auto text-xs font-normal text-slate-500">
            Add, edit, or delete monitored URLs
          </span>
        </button>
        {configOpen && (
          <div className="space-y-6 border-t border-avline p-3">
            {crudError && (
              <div className="rounded border border-rose-800 bg-rose-950/40 px-3 py-2 text-sm text-rose-100">
                {crudError}
              </div>
            )}
            <form onSubmit={submitCreate} className="space-y-3">
              <h3 className="text-sm font-medium text-slate-300">Add endpoint</h3>
              <EndpointFormFields
                value={createForm}
                onChange={setCreateForm}
                idPrefix="create"
              />
              <button
                type="submit"
                disabled={busy}
                className="rounded border border-blue-600 bg-blue-950/40 px-3 py-1.5 text-sm text-blue-100 hover:bg-blue-900/40 disabled:opacity-50"
              >
                Save new endpoint
              </button>
            </form>

            <div>
              <h3 className="mb-2 text-sm font-medium text-slate-300">
                Existing endpoints
              </h3>
              <div className="overflow-x-auto rounded border border-avline/80">
                <table className="w-full min-w-[640px] border-collapse text-left text-sm">
                  <thead>
                    <tr className="border-b border-avline text-xs uppercase text-slate-500">
                      <th className="px-2 py-2">Name</th>
                      <th className="px-2 py-2">URL</th>
                      <th className="px-2 py-2">Method</th>
                      <th className="px-2 py-2 w-28">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.endpoints || []).map((e) => (
                      <tr
                        key={e.id}
                        className="border-b border-avline/60 hover:bg-slate-900/30"
                      >
                        <td className="px-2 py-2 text-slate-200">{e.name}</td>
                        <td className="max-w-[14rem] truncate px-2 py-2 text-xs text-slate-500" title={e.url}>
                          {e.url}
                        </td>
                        <td className="px-2 py-2 text-slate-400">{e.method}</td>
                        <td className="px-2 py-2">
                          <div className="flex flex-wrap gap-1">
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => startEdit(e)}
                              className="inline-flex items-center gap-1 rounded border border-avline px-2 py-1 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-50"
                            >
                              <Pencil className="h-3 w-3" />
                              Edit
                            </button>
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => void removeEndpoint(e.id, e.name)}
                              className="inline-flex items-center gap-1 rounded border border-rose-900/60 px-2 py-1 text-xs text-rose-200 hover:bg-rose-950/50 disabled:opacity-50"
                            >
                              <Trash2 className="h-3 w-3" />
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!(data?.endpoints || []).length && (
                  <p className="p-3 text-sm text-slate-500">No endpoints yet.</p>
                )}
              </div>
            </div>

            {editingId && (
              <form onSubmit={submitEdit} className="space-y-3 rounded border border-blue-900/50 bg-blue-950/20 p-3">
                <h3 className="text-sm font-medium text-blue-200">Edit endpoint</h3>
                <EndpointFormFields
                  value={editForm}
                  onChange={setEditForm}
                  idPrefix="edit"
                />
                <div className="flex flex-wrap gap-2">
                  <button
                    type="submit"
                    disabled={busy}
                    className="rounded border border-blue-600 bg-blue-950/40 px-3 py-1.5 text-sm text-blue-100 hover:bg-blue-900/40 disabled:opacity-50"
                  >
                    Save changes
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={cancelEdit}
                    className="rounded border border-avline px-3 py-1.5 text-sm text-slate-300 hover:bg-slate-800 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            )}
          </div>
        )}
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
