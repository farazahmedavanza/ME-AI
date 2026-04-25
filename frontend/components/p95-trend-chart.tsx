"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const COLS = ["#EF4444", "#3B82F6", "#22C55E", "#A855F7", "#F59E0B"];

type Series = { name: string; points: { x: number; y: number }[] };

function mergeChart(series: Series[]) {
  const byX: Record<number, Record<string, number>> = {};
  for (const s of series) {
    for (const p of s.points) {
      if (!byX[p.x]) {
        byX[p.x] = {} as Record<string, number>;
      }
      byX[p.x][s.name] = p.y;
      byX[p.x].x = p.x;
    }
  }
  return Object.values(byX)
    .sort((a, b) => a.x - b.x)
    .map((row) => {
      const o: Record<string, number> = { index: row.x };
      for (const s of series) {
        const v = row[s.name];
        if (v !== undefined && !Number.isNaN(v)) {
          o[s.name] = v;
        }
      }
      return o;
    });
}

export function P95TrendChart({ series }: { series: Series[] }) {
  const data = mergeChart(series);
  const names = series.map((s) => s.name);
  return (
    <div className="rounded border border-avline bg-slate-900/30 p-2">
      <div className="px-1 pb-2 text-sm font-medium text-slate-200">
        Response time (P95) trend
      </div>
      <div className="h-64 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="index"
              tick={{ fontSize: 10, fill: "#94a3b8" }}
              stroke="#334155"
            />
            <YAxis
              tick={{ fontSize: 10, fill: "#94a3b8" }}
              stroke="#334155"
              label={{
                value: "ms",
                angle: -90,
                position: "insideLeft",
                fill: "#64748b",
                fontSize: 10,
              }}
            />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #334155" }}
            />
            <Legend />
            {names.map((n, i) => (
              <Line
                key={n}
                type="monotone"
                dataKey={n}
                name={n}
                stroke={COLS[i % COLS.length]}
                dot={false}
                strokeWidth={2}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
