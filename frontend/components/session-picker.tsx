"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type Sess = { id: string; filename: string; uploaded_at: string; log_count: number; status: string };

export function SessionPicker({
  currentSessionId,
  onSessionChange,
}: {
  currentSessionId: string | null;
  onSessionChange: (id: string | null) => void;
}) {
  const [list, setList] = useState<Sess[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const load = async () => {
    setErr(null);
    try {
      const r = await apiGet("/api/sessions");
      if (!r.ok) throw new Error(await r.text());
      const d = (await r.json()) as { sessions: Sess[] };
      setList(d.sessions || []);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load sessions");
    }
  };

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="rounded border border-avline bg-slate-900/40 px-3 py-2 text-xs">
      <div className="mb-1 flex items-center justify-between text-slate-500">
        <span>Log sessions</span>
        <button
          type="button"
          onClick={() => void load()}
          className="text-blue-400 hover:underline"
        >
          Refresh
        </button>
      </div>
      <select
        className="w-full max-w-md rounded border border-avline bg-slate-950 px-2 py-1.5 text-slate-200"
        value={currentSessionId || ""}
        onChange={(e) => onSessionChange(e.target.value || null)}
      >
        <option value="">Latest session (default)</option>
        {list.map((s) => (
          <option key={s.id} value={s.id}>
            {s.filename} — {s.log_count ?? "?"} rows — {s.uploaded_at?.slice(0, 19)}
          </option>
        ))}
      </select>
      {err && <p className="mt-1 text-rose-400">{err}</p>}
    </div>
  );
}
