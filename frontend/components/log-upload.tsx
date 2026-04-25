"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";

export function LogUpload({ onDone }: { onDone: () => void }) {
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <div className="rounded border border-avline border-dashed border-slate-600 bg-slate-950/30 p-3 text-xs text-slate-400">
      <div className="text-slate-200">Upload API logs (JSON array)</div>
      <input
        type="file"
        accept="application/json"
        className="mt-2 w-full"
        onChange={async (e) => {
          const f = e.target.files?.[0];
          if (!f) return;
          setBusy(true);
          setMsg(null);
          try {
            const text = await f.text();
            const logs = JSON.parse(text);
            if (!Array.isArray(logs)) throw new Error("File must be a JSON array of log entries");
            const r = await apiPost("/api/upload-logs", {
              filename: f.name,
              logs,
            });
            if (!r.ok) throw new Error(await r.text());
            setMsg("Upload successful.");
            onDone();
          } catch (err) {
            setMsg(err instanceof Error ? err.message : "Upload failed");
          } finally {
            setBusy(false);
          }
        }}
      />
      {busy && <p className="mt-1">Uploading…</p>}
      {msg && <p className="mt-1 text-slate-500">{msg}</p>}
    </div>
  );
}
