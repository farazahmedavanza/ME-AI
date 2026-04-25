"use client";

import {
  Line,
  LineChart,
  ResponsiveContainer,
} from "recharts";
import { cn } from "@/lib/cn";

type E = {
  service: string;
  api_label: string;
  endpoint: string;
  risk_tag: string;
  trend_sparkline: number[];
  breach_probability: number;
  minutes_to_breach: number | null;
  sla_risk: string;
};

function MiniRisk({ up }: { up: boolean }) {
  const d = up
    ? [10, 12, 18, 25, 35, 48]
    : [40, 38, 36, 35, 34, 33];
  const pts = d.map((v, i) => ({ i, v }));
  return (
    <div className="h-8 w-20">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={pts}>
          <Line
            type="monotone"
            dataKey="v"
            stroke={up ? "#EF4444" : "#F59E0B"}
            dot={false}
            strokeWidth={1.5}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function SlaBreachPredictorList({ items }: { items: E[] }) {
  const bad = items.filter(
    (x) => x.sla_risk === "red" || x.sla_risk === "amber"
  );
  return (
    <div className="flex h-full flex-col rounded border border-avline bg-slate-900/30">
      <div className="border-b border-avline px-3 py-2 text-sm font-medium text-slate-200">
        AI SLA Breach Predictor
      </div>
      <div className="max-h-[360px] space-y-2 overflow-y-auto p-2">
        {bad.length === 0 && (
          <p className="p-2 text-xs text-slate-500">No high-risk signals in window.</p>
        )}
        {bad.map((e) => {
          const high = e.sla_risk === "red";
          const m = e.minutes_to_breach;
          return (
            <div
              key={e.service}
              className="flex items-start justify-between gap-2 rounded border border-avline/60 bg-slate-950/40 p-2"
            >
              <div className="min-w-0">
                <div className="truncate text-sm font-medium text-slate-100">
                  {e.api_label}
                </div>
                <div className="truncate text-[11px] text-slate-500">{e.endpoint}</div>
                <div className="mt-1 text-[11px] text-slate-400">
                  {Math.round(e.breach_probability * 100)}% chance of SLA breach
                  {m != null ? ` in ${m} min` : ""}
                </div>
              </div>
              <div className="flex flex-col items-end gap-1">
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 text-[10px] font-bold uppercase",
                    high
                      ? "bg-red-500/20 text-red-300"
                      : "bg-amber-500/20 text-amber-200"
                  )}
                >
                  {high ? "High risk" : "Medium risk"}
                </span>
                <MiniRisk up={high} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
