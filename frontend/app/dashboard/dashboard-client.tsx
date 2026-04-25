"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { KpiRow } from "@/components/kpi-row";
import { HealthOverviewTable } from "@/components/health-overview-table";
import { SlaBreachPredictorList } from "@/components/sla-breach-predictor-list";
import { P95TrendChart } from "@/components/p95-trend-chart";
import { AiLogSearch } from "@/components/ai-log-search";
import { AlertTimeline } from "@/components/alert-timeline";
import { IncidentReportPanel } from "@/components/incident-report-panel";
import { DegradedModeBanner } from "@/components/degraded-mode-banner";
import { LogUpload } from "@/components/log-upload";
import { SessionPicker } from "@/components/session-picker";
import { AddWidgetButton } from "@/components/add-widget-dialog";
import { ToastBar } from "@/components/toast-bar";
import { LiveMonitoringWidget } from "@/components/live-monitoring-widget";
import { apiGet, getHealth } from "@/lib/api";

type DashboardPayload = {
  data: {
    kpis: {
      total_apis: number;
      overall_uptime_pct: number;
      avg_response_ms: number;
      error_rate_pct: number;
      sla_breach_donut: { red: number; amber: number; green: number };
    };
    endpoints: {
      service: string;
      api_label: string;
      endpoint: string;
      status: string;
      sla_risk: string;
      p95_ms: number;
      p95_delta_pct: number;
      error_rate: number;
      error_delta_pp: number;
      uptime_30m_pct: number;
      trend_sparkline: number[];
      breach_probability: number;
      minutes_to_breach: number | null;
      risk_tag: string;
    }[];
    p95_chart: { name: string; points: { x: number; y: number }[] }[];
  };
  alerts: {
    id: string;
    created_at: string;
    title?: string;
    description?: string;
    severity: string;
    resolution_status: string;
    assignee?: string;
    api_label?: string;
    endpoint?: string;
  }[];
  session_id: string | null;
  empty?: boolean;
  ai?: string;
};

export function DashboardClient() {
  const router = useRouter();
  const sp = useSearchParams();
  const [range, setRange] = useState("1h");
  const [auto, setAuto] = useState(true);
  const [dash, setDash] = useState<DashboardPayload | null>(null);
  const [ai, setAi] = useState("local");
  const [initialError, setInitialError] = useState<string | null>(null);
  const firstFetch = useRef(true);
  const [toast, setToast] = useState<{
    msg: string;
    kind: "error" | "success" | "info";
  } | null>(null);
  const urlSession = sp.get("session");
  const [sessionId, setSessionId] = useState<string | null>(urlSession);

  useEffect(() => {
    setSessionId(urlSession);
  }, [urlSession]);

  const onSessionChange = (id: string | null) => {
    setSessionId(id);
    const p = new URLSearchParams(sp.toString());
    if (id) p.set("session", id);
    else p.delete("session");
    const qs = p.toString();
    router.push(qs ? `/dashboard?${qs}` : "/dashboard");
  };

  const load = useCallback(async () => {
    const q = new URLSearchParams();
    q.set("range", range);
    if (sessionId) q.set("session_id", sessionId);
    const r = await apiGet(`/api/dashboard?${q.toString()}`);
    if (!r.ok) {
      const t = await r.text();
      setToast({ msg: t, kind: "error" });
      if (firstFetch.current) setInitialError(t);
      return;
    }
    firstFetch.current = false;
    setInitialError(null);
    const d = (await r.json()) as DashboardPayload;
    setDash(d);
    if (d.ai) setAi(d.ai);
  }, [range, sessionId]);

  useEffect(() => {
    getHealth()
      .then((h) => {
        if (h.ai) setAi(h.ai);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!auto) return;
    const t = setInterval(() => {
      void load();
    }, 30_000);
    return () => clearInterval(t);
  }, [auto, load]);

  if (initialError && !dash) {
    return (
      <div className="rounded border border-rose-800 bg-rose-950/40 p-4 text-rose-200">
        <p className="font-medium">Could not load dashboard</p>
        <p className="mt-1 text-sm opacity-90">{initialError}</p>
        <button
          type="button"
          onClick={() => {
            firstFetch.current = true;
            setInitialError(null);
            void load();
          }}
          className="mt-3 rounded bg-rose-900/50 px-3 py-1 text-sm"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!dash) {
    return (
      <div className="text-slate-500">
        <DegradedModeBanner />
        <p>Loading…</p>
      </div>
    );
  }

  if (dash.empty || !dash.data) {
    return (
      <div className="space-y-3">
        <DegradedModeBanner />
        <SessionPicker
          currentSessionId={sessionId}
          onSessionChange={onSessionChange}
        />
        <LiveMonitoringWidget
          autoRefresh
          refreshMs={30_000}
          onImportedLiveLogs={() => {
            void load();
            setToast({
              msg: "Overview updated from live monitoring export.",
              kind: "success",
            });
          }}
        />
        <p className="text-slate-400">
          No log session yet. Start the API and wait for seed, or upload JSON.
        </p>
        <LogUpload
          onDone={() => {
            void load();
            setToast({ msg: "Logs uploaded. Dashboard refreshed.", kind: "success" });
          }}
        />
        {toast && (
          <ToastBar
            message={toast.msg}
            kind={toast.kind}
            onClose={() => setToast(null)}
          />
        )}
      </div>
    );
  }

  const s = dash.session_id;
  return (
    <div className="space-y-4">
      {toast && (
        <ToastBar
          message={toast.msg}
          kind={toast.kind}
          onClose={() => setToast(null)}
        />
      )}
      <DegradedModeBanner />
      <SessionPicker
        currentSessionId={sessionId}
        onSessionChange={onSessionChange}
      />
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold text-white">
              API Health & SLA monitor
            </h1>
            <span className="rounded-full bg-violet-600/20 px-2 py-0.5 text-xs font-semibold text-violet-200">
              AI powered
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-slate-300">
          <label className="flex items-center gap-1">
            Window
            <select
              className="rounded border border-avline bg-slate-900 px-2 py-1"
              value={range}
              onChange={(e) => setRange(e.target.value)}
            >
              <option value="15m">15 min</option>
              <option value="1h">1 h</option>
              <option value="6h">6 h</option>
              <option value="24h">24 h</option>
            </select>
          </label>
          <label className="flex items-center gap-1">
            <input
              type="checkbox"
              checked={auto}
              onChange={(e) => setAuto(e.target.checked)}
            />
            Auto-refresh 30s
          </label>
          <AddWidgetButton />
        </div>
      </header>

      <KpiRow kpis={dash.data.kpis} />
      <LiveMonitoringWidget
        autoRefresh={auto}
        refreshMs={30_000}
        onImportedLiveLogs={() => {
          void load();
          setToast({
            msg: "Overview updated from live monitoring export.",
            kind: "success",
          });
        }}
      />
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-2" id="apis">
        <div id="sla">
          <HealthOverviewTable rows={dash.data.endpoints} />
        </div>
        <SlaBreachPredictorList items={dash.data.endpoints} />
      </div>
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-1">
        <P95TrendChart series={dash.data.p95_chart} />
      </div>
      <div
        className="grid grid-cols-1 gap-3 lg:grid-cols-3"
        id="search"
      >
        <div className="lg:col-span-1" id="alerts">
          <AiLogSearch sessionId={s} />
        </div>
        <div className="lg:col-span-1">
          <AlertTimeline
            alerts={dash.alerts}
            onChange={() => void load()}
          />
        </div>
        <div className="lg:col-span-1" id="incident">
          <IncidentReportPanel sessionId={s} ai={ai} rangeKey={range} />
        </div>
      </div>
      <div className="grid max-w-md gap-2 text-xs" id="settings">
        <LogUpload
          onDone={() => {
            void load();
            setToast({ msg: "Upload complete. Session list updated.", kind: "success" });
          }}
        />
        <a href="#apis" className="text-slate-500">
          Anchor: APIs, alerts, incident, search, settings
        </a>
        <a href="/upload" className="text-blue-400 hover:underline">
          Open dedicated upload view
        </a>
      </div>
    </div>
  );
}
