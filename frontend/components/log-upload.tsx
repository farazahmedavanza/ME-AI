"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";
import {
  parseRdvOrTextLogFile,
  parseUploadJsonFile,
} from "@/lib/log-upload-parsers";

export function LogUpload({ onDone }: { onDone: () => void }) {
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  async function postLogs(filename: string, logs: Record<string, unknown>[]) {
    const r = await apiPost("/api/upload-logs", { filename, logs });
    if (!r.ok) throw new Error(await r.text());
  }

  return (
    <div className="space-y-4 text-xs text-slate-400">
      <p className="text-slate-500">
        If your export is a single <span className="text-slate-300">JSON array</span> of log
        objects, or a <span className="text-slate-300">live_monitor_logs_v1</span> wrapper from
        Live Monitoring, use <span className="text-slate-300">JSON</span>. If it is a service log with plain text
        and XML, use <span className="text-slate-300">Other log file</span>.
      </p>

      <div className="rounded border border-avline border-dashed border-slate-600 bg-slate-950/30 p-3">
        <div className="text-slate-200">Upload JSON (API logs)</div>
        <p className="mt-1 text-slate-500">
          One JSON file containing an array of log objects (see{" "}
          <code className="text-slate-400">backend/data/api_logs.json</code>).
        </p>
        <input
          type="file"
          accept="application/json,.json"
          className="mt-2 w-full"
          disabled={busy}
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            setBusy(true);
            setMsg(null);
            try {
              const text = await f.text();
              const logs = parseUploadJsonFile(text);
              await postLogs(f.name, logs);
              setMsg("JSON upload successful.");
              onDone();
            } catch (err) {
              setMsg(err instanceof Error ? err.message : "Upload failed");
            } finally {
              setBusy(false);
              e.target.value = "";
            }
          }}
        />
      </div>

      <div className="rounded border border-avline border-dashed border-slate-600 bg-slate-950/30 p-3">
        <div className="text-slate-200">Import text / Rdv / other log file</div>
        <p className="mt-1 text-slate-500">
          Plain text or <code className="text-slate-400">.log</code> — not a single JSON array.
          Rdv-style logs: lines with <code className="text-slate-400">Rest Response Message</code> and
          XML such as <code className="text-slate-400">RdvStatusCode</code>, <code className="text-slate-400">RdvMessageId</code>.
        </p>
        <input
          type="file"
          accept="text/plain,.txt,.log"
          className="mt-2 w-full"
          disabled={busy}
          onChange={async (e) => {
            const f = e.target.files?.[0];
            if (!f) return;
            setBusy(true);
            setMsg(null);
            try {
              const text = await f.text();
              const { logs, warnings } = parseRdvOrTextLogFile(text, f.name);
              if (logs.length === 0) {
                setMsg(
                  warnings.length > 0
                    ? `No log entries could be parsed. ${warnings.join(" ")}`
                    : "No log entries could be parsed from this file."
                );
                e.target.value = "";
                return;
              }
              await postLogs(f.name, logs);
              const extra = warnings.length ? ` ${warnings.join(" ")}` : "";
              setMsg(`Upload successful (${logs.length} row(s)).${extra}`);
              onDone();
            } catch (err) {
              setMsg(err instanceof Error ? err.message : "Upload failed");
            } finally {
              setBusy(false);
              e.target.value = "";
            }
          }}
        />
      </div>

      {busy && <p className="text-slate-500">Uploading…</p>}
      {msg && <p className="text-slate-500">{msg}</p>}
    </div>
  );
}
