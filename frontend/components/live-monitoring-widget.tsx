"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Activity, ChevronRight, Download } from "lucide-react";
import { cn } from "@/lib/cn";
import {
  apiPost,
  getLiveMonitoringLogsExport,
  getLiveMonitoringSnapshot,
  type LiveMonitoringSnapshot,
} from "@/lib/api";

const LM_IMPORT_KEY = "avanza_lm_last_import_exported_at";

function healthLabel(h: string) {
  if (h === "healthy") return { text: "Healthy", className: "text-emerald-400" };
  if (h === "degraded") return { text: "Degraded", className: "text-amber-400" };
  if (h === "no_endpoints") return { text: "No endpoints", className: "text-slate-500" };
  return { text: h || "Unknown", className: "text-slate-400" };
}

export function LiveMonitoringWidget({
  autoRefresh,
  refreshMs = 30_000,
  onImportedLiveLogs,
}: {
  autoRefresh: boolean;
  refreshMs?: number;
  /** Called after a new snapshot is auto-imported to Overview via /api/upload-logs. */
  onImportedLiveLogs?: () => void;
}) {
  const [snap, setSnap] = useState<LiveMonitoringSnapshot | null | undefined>(
    undefined,
  );
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      setError(null);
      const s = await getLiveMonitoringSnapshot();
      setSnap(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not load snapshot");
      setSnap(undefined);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!autoRefresh) return;
    const t = setInterval(() => void load(), refreshMs);
    return () => clearInterval(t);
  }, [autoRefresh, refreshMs, load]);

  useEffect(() => {
    if (snap === undefined || snap === null) return;
    const logs = snap.synthetic_api_logs;
    if (!logs?.length) return;
    const ex = snap.exported_at;
    if (!ex) return;
    try {
      if (
        typeof sessionStorage !== "undefined" &&
        sessionStorage.getItem(LM_IMPORT_KEY) === ex
      ) {
        return;
      }
    } catch {
      /* ignore */
    }
    void (async () => {
      try {
        const r = await apiPost("/api/upload-logs", {
          filename: `live_monitor_${ex.replace(/[:.]/g, "-")}.json`,
          logs,
        });
        if (r.ok) {
          try {
            sessionStorage.setItem(LM_IMPORT_KEY, ex);
          } catch {
            /* ignore */
          }
          onImportedLiveLogs?.();
        }
      } catch {
        /* avoid toast spam */
      }
    })();
  }, [snap, onImportedLiveLogs]);

  async function downloadExport() {
    let logs = snap?.synthetic_api_logs;
    if (!logs?.length) {
      try {
        logs = (await getLiveMonitoringLogsExport()) ?? undefined;
      } catch {
        return;
      }
    }
    if (!logs?.length) return;
    const blob = new Blob([JSON.stringify(logs, null, 2)], {
      type: "application/json",
    });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `live_monitor_api_logs_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  if (error) {
    return (
      <div className="rounded border border-rose-900/50 bg-rose-950/20 px-3 py-2 text-sm text-rose-200">
        <span className="font-medium">Live monitoring snapshot</span>
        <p className="mt-1 text-xs opacity-90">{error}</p>
      </div>
    );
  }

  if (snap === undefined) {
    return (
      <div className="rounded border border-avline bg-slate-950/40 px-3 py-2 text-sm text-slate-500">
        <span className="inline-flex items-center gap-2">
          <Activity className="h-4 w-4 animate-pulse" />
          Loading live monitoring summary…
        </span>
      </div>
    );
  }

  if (snap === null) {
    return (
      <div className="rounded border border-avline bg-slate-950/40 px-3 py-3 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <div className="font-medium text-slate-200">Live monitoring</div>
            <p className="mt-0.5 text-xs text-slate-500">
              No server snapshot yet (updates every few minutes). Open Live Monitoring
              to run checks.
            </p>
          </div>
          <Link
            href="/live-monitoring"
            className="inline-flex items-center gap-1 text-xs text-blue-400 hover:underline"
          >
            Open <ChevronRight className="h-3 w-3" />
          </Link>
        </div>
      </div>
    );
  }

  const hl = healthLabel(snap.overall_health);
  const pct = snap.kpis.pct_up;
  const hasExport = (snap.synthetic_api_logs?.length ?? 0) > 0;
  const canDownload = hasExport || (snap.endpoints?.length ?? 0) > 0;

  return (
    <div className="rounded border border-avline bg-slate-950/40 px-3 py-3 text-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Activity className="h-4 w-4 text-blue-400" aria-hidden />
            <span className="font-medium text-slate-200">Live monitoring</span>
            <span className={cn("text-xs font-semibold", hl.className)}>
              {hl.text}
            </span>
          </div>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
            <span>
              Exported{" "}
              {snap.exported_at
                ? new Date(snap.exported_at).toLocaleString()
                : "—"}
            </span>
            {snap.last_run_at && (
              <span>Last check run {new Date(snap.last_run_at).toLocaleString()}</span>
            )}
            <span>
              {snap.kpis.enabled_count}/{snap.kpis.total_endpoints} enabled
            </span>
            {pct != null && (
              <span className="text-slate-400">{pct.toFixed(0)}% up (enabled)</span>
            )}
            <span>Open alerts: {snap.open_alerts_count}</span>
            <span>Recent (24h): {snap.recent_alerts_count}</span>
            <span>SLA breaches: {snap.kpis.breach_count}</span>
          </div>
          {hasExport && (
            <p className="mt-2 text-xs text-slate-500">
              New snapshots auto-import to Overview as API log rows. You can also download
              the JSON and use <span className="text-slate-400">Upload JSON (API logs)</span>.
            </p>
          )}
        </div>
        <div className="flex shrink-0 flex-col gap-1.5">
          <Link
            href="/live-monitoring"
            className="inline-flex items-center justify-center gap-1 rounded border border-avline px-2 py-1 text-xs text-slate-300 hover:border-slate-500 hover:bg-slate-900"
          >
            Details <ChevronRight className="h-3 w-3" />
          </Link>
          {canDownload && (
            <button
              type="button"
              onClick={() => void downloadExport()}
              className="inline-flex items-center justify-center gap-1 rounded border border-avline px-2 py-1 text-xs text-slate-300 hover:border-slate-500 hover:bg-slate-900"
            >
              <Download className="h-3 w-3" />
              Download logs JSON
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
