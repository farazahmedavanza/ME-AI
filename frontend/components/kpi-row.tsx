"use client";

import {
  Line,
  LineChart,
  Pie,
  PieChart,
  Cell,
  ResponsiveContainer,
} from "recharts";

type K = {
  total_apis: number;
  overall_uptime_pct: number;
  avg_response_ms: number;
  error_rate_pct: number;
  sla_breach_donut: { red: number; amber: number; green: number };
};

const COL = { red: "#EF4444", amber: "#F59E0B", green: "#22C55E" };

function MiniUptime() {
  const d = [99.1, 99.0, 99.2, 99.32, 99.1];
  return (
    <ResponsiveContainer width="100%" height={32}>
      <LineChart data={d.map((v, i) => ({ i, v }))}>
        <Line
          type="monotone"
          dataKey="v"
          stroke="#22C55E"
          dot={false}
          strokeWidth={2}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

export function KpiRow({ kpis }: { kpis: K }) {
  const donut = [
    { name: "High", v: kpis.sla_breach_donut.red, c: COL.red },
    { name: "Med", v: kpis.sla_breach_donut.amber, c: COL.amber },
    { name: "Low", v: kpis.sla_breach_donut.green, c: COL.green },
  ];
  return (
    <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
      <Kpi
        label="Total APIs"
        value={String(kpis.total_apis)}
        subCls="text-emerald-400"
        subText="+2 vs yesterday"
      />
      <Kpi
        label="Overall Uptime"
        value={`${kpis.overall_uptime_pct.toFixed(2)}%`}
        subCls="text-emerald-400"
        subText="+0.41%"
        chart={<MiniUptime />}
      />
      <Kpi
        label="Avg Response Time"
        value={`${Math.round(kpis.avg_response_ms)} ms`}
        subCls="text-rose-400"
        subText="+18% vs last hour"
      />
      <Kpi
        label="Error rate (Overall)"
        value={`${kpis.error_rate_pct.toFixed(2)}%`}
        subCls="text-rose-400"
        subText="+1.08% vs last hour"
      />
      <div className="rounded border border-avline bg-slate-900/50 p-3">
        <div className="text-xs font-medium text-slate-500">SLA Breach risk</div>
        <div className="mt-1 flex h-20 items-center gap-2">
          <ResponsiveContainer width="50%" height="100%">
            <PieChart>
              <Pie
                data={donut}
                dataKey="v"
                nameKey="name"
                innerRadius={18}
                outerRadius={32}
                paddingAngle={2}
              >
                {donut.map((e, i) => (
                  <Cell key={i} fill={e.c} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="flex-1 text-xs text-slate-300">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded bg-red-500" />
              {kpis.sla_breach_donut.red} high
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded bg-amber-500" />
              {kpis.sla_breach_donut.amber} medium
            </div>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded bg-emerald-500" />
              {kpis.sla_breach_donut.green} low
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Kpi({
  label,
  value,
  subCls,
  subText,
  chart,
}: {
  label: string;
  value: string;
  subCls: string;
  subText: string;
  chart?: React.ReactNode;
}) {
  return (
    <div className="rounded border border-avline bg-slate-900/50 p-3">
      <div className="text-xs font-medium text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-white">{value}</div>
      <div className={`text-xs ${subCls} mt-1`}>{subText}</div>
      {chart}
    </div>
  );
}
