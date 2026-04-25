"use client";

import {
  Line,
  LineChart,
  ResponsiveContainer,
} from "recharts";
import { cn } from "@/lib/cn";

type Row = {
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
};

const riskCls: Record<string, string> = {
  red: "bg-red-500/20 text-red-300",
  amber: "bg-amber-500/20 text-amber-200",
  green: "bg-emerald-500/20 text-emerald-200",
};

function Spark({ data }: { data: number[] }) {
  const pts = data.map((v, i) => ({ i, v }));
  return (
    <div className="h-8 w-24">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={pts}>
          <Line
            type="monotone"
            dataKey="v"
            stroke="#3B82F6"
            dot={false}
            strokeWidth={1.5}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function HealthOverviewTable({ rows }: { rows: Row[] }) {
  return (
    <div className="overflow-x-auto rounded border border-avline bg-slate-900/30">
      <div className="border-b border-avline px-3 py-2 text-sm font-medium text-slate-200">
        API Health overview
      </div>
      <table className="w-full min-w-[900px] text-left text-xs text-slate-300">
        <thead className="text-slate-500">
          <tr>
            <th className="px-3 py-2">API / Endpoint</th>
            <th className="px-2 py-2">Status</th>
            <th className="px-2 py-2">SLA</th>
            <th className="px-2 py-2">P95</th>
            <th className="px-2 py-2">Error</th>
            <th className="px-2 py-2">Uptime(30m)</th>
            <th className="px-2 py-2">30m</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.service + r.endpoint} className="border-t border-avline/60">
              <td className="px-3 py-2">
                <div className="font-medium text-slate-100">{r.api_label}</div>
                <div className="text-slate-500">{r.endpoint}</div>
              </td>
              <td className="px-2 py-2 text-slate-200">{r.status}</td>
              <td className="px-2 py-2">
                <span
                  className={cn(
                    "inline-flex rounded px-2 py-0.5 text-[10px] font-semibold uppercase",
                    riskCls[r.sla_risk] || "bg-slate-700/40"
                  )}
                >
                  {r.sla_risk}
                </span>
              </td>
              <td className="px-2 py-2">
                <div>{r.p95_ms} ms</div>
                <div
                  className={r.p95_delta_pct > 0 ? "text-rose-400" : "text-emerald-400"}
                >
                  {r.p95_delta_pct > 0 ? "↑" : "↓"}{" "}
                  {Math.abs(r.p95_delta_pct).toFixed(0)}%
                </div>
              </td>
              <td className="px-2 py-2">
                <div>{r.error_rate}%</div>
                <div className="text-rose-300">↑ {r.error_delta_pp.toFixed(2)}</div>
              </td>
              <td className="px-2 py-2">{r.uptime_30m_pct}%</td>
              <td className="px-2 py-2">
                <Spark data={r.trend_sparkline} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
