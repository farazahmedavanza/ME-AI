"use client";

import { apiPatch } from "@/lib/api";
import { cn } from "@/lib/cn";

type Alert = {
  id: string;
  created_at: string;
  title?: string;
  description?: string;
  severity: string;
  resolution_status: string;
  assignee?: string;
  api_label?: string;
  endpoint?: string;
};

const sevColor: Record<string, string> = {
  high: "border-l-rose-500",
  low: "border-l-emerald-500",
  medium: "border-l-amber-500",
};

export function AlertTimeline({ alerts, onChange }: { alerts: Alert[]; onChange: () => void }) {
  return (
    <div className="flex flex-col rounded border border-avline bg-slate-900/30 p-2">
      <div className="px-1 pb-2 text-sm font-medium text-slate-200">Alert timeline</div>
      <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
        {alerts.length === 0 && (
          <p className="text-xs text-slate-500">No alerts in this session.</p>
        )}
        {alerts.map((a) => (
          <div
            key={a.id}
            className={cn(
              "rounded border-l-2 border border-avline/60 border-l-4 bg-slate-950/30 p-2 pl-2",
              sevColor[a.severity] || "border-l-slate-500"
            )}
          >
            <div className="text-[10px] text-slate-500">
              {a.created_at?.replace("T", " ").slice(0, 16)}
            </div>
            <div className="text-sm text-slate-100">{a.title || "Alert"}</div>
            <div className="text-[11px] text-slate-400">
              {a.api_label} · {a.endpoint}
            </div>
            <div className="mt-1 text-[11px] text-slate-500">
              {a.description}
            </div>
            <div className="mt-2 flex items-center justify-between text-[10px]">
              <span className="rounded bg-slate-800/80 px-1.5 py-0.5 text-slate-300">
                {a.resolution_status}
              </span>
              <span className="text-slate-500">{a.assignee}</span>
            </div>
            {a.resolution_status !== "resolved" && (
              <div className="mt-2 flex gap-1">
                {["open", "investigating", "resolved"].map((s) => (
                  <button
                    key={s}
                    type="button"
                    className="rounded border border-avline px-1.5 py-0.5 text-[10px] text-slate-300 hover:bg-slate-800"
                    onClick={async () => {
                      const r = await apiPatch(`/api/alerts/${a.id}`, {
                        resolution_status: s,
                      });
                      if (r.ok) onChange();
                    }}
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
