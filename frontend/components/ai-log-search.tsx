"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";

export function AiLogSearch({ sessionId }: { sessionId: string | null }) {
  const [q, setQ] = useState("show me all 5xx errors in the last 2 hours");
  const [rows, setRows] = useState<Record<string, unknown>[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onSearch() {
    if (!sessionId) return;
    setLoading(true);
    setErr(null);
    try {
      const r = await apiPost("/api/log-search", {
        session_id: sessionId,
        query: q,
      });
      if (!r.ok) throw new Error(await r.text());
      const d = (await r.json()) as { rows: Record<string, unknown>[]; parsed_filters: unknown };
      setRows(d.rows);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col rounded border border-avline bg-slate-900/30 p-2">
      <div className="px-1 pb-2 text-sm font-medium text-slate-200">AI log search</div>
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-avline bg-slate-950/60 px-2 py-1.5 text-xs text-slate-200"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        <button
          type="button"
          onClick={onSearch}
          disabled={!sessionId || loading}
          className="rounded bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
        >
          {loading ? "…" : "Search"}
        </button>
      </div>
      {err && <p className="mt-1 text-xs text-rose-400">{err}</p>}
      <div className="mt-2 max-h-56 overflow-auto">
        <table className="w-full min-w-[600px] text-left text-[11px] text-slate-300">
          <thead className="text-slate-500">
            <tr>
              <th className="py-1">Time</th>
              <th>API / Endpoint</th>
              <th>Status</th>
              <th>RT (ms)</th>
              <th>Error</th>
              <th>Request id</th>
            </tr>
          </thead>
          <tbody>
            {(rows || []).slice(0, 30).map((r, i) => (
              <tr key={i} className="border-t border-avline/50">
                <td className="py-0.5 pr-2 text-slate-500">
                  {String(r.timestamp).slice(11, 19)}
                </td>
                <td className="pr-2">
                  <div className="text-slate-200">{String(r.api_label || r.service || "")}</div>
                  <div className="text-slate-500">{String(r.endpoint || "")}</div>
                </td>
                <td className="pr-2">{String(r.status_code)}</td>
                <td className="pr-2">{String(r.response_time_ms)}</td>
                <td className="pr-2 text-rose-300">
                  {r.error_message ? String(r.error_message) : "—"}
                </td>
                <td className="text-slate-500">{String(r.trace_id || r.id || "")}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows && rows.length === 0 && (
          <p className="p-2 text-xs text-slate-500">No matches.</p>
        )}
      </div>
    </div>
  );
}
