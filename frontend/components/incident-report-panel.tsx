"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";

export function IncidentReportPanel({
  sessionId,
  ai,
}: {
  sessionId: string | null;
  ai: "openrouter" | "local" | string;
}) {
  const [text, setText] = useState(
    "Generate a new report to see a three-paragraph operations summary for the worst-affected API in the current log window. If the generative model is not configured, a deterministic template is used."
  );
  const [mode, setMode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function generate() {
    if (!sessionId) return;
    setLoading(true);
    try {
      const r = await apiPost("/api/incident-report", { session_id: sessionId });
      if (!r.ok) throw new Error(await r.text());
      const d = (await r.json()) as { text: string; ai_mode: string };
      setText(d.text);
      setMode(d.ai_mode);
    } finally {
      setLoading(false);
    }
  }

  function printReport() {
    const w = window.open("", "PRINT", "height=800,width=700");
    if (!w) return;
    w.document.write(
      `<pre style="font-family:system-ui;padding:20px;white-space:pre-wrap;">${text.replace(
        /</g,
        "&lt;"
      )}</pre>`
    );
    w.document.close();
    w.print();
  }

  return (
    <div className="flex h-full min-h-[240px] flex-col rounded border border-avline bg-slate-900/30 p-2">
      <div className="flex items-center justify-between border-b border-avline pb-2">
        <div className="text-sm font-medium text-slate-200">AI Incident Report</div>
        <button
          type="button"
          onClick={generate}
          disabled={!sessionId || loading}
          className="rounded border border-slate-600 bg-slate-800 px-2 py-1 text-[11px] text-slate-200 hover:bg-slate-700"
        >
          {loading ? "Working…" : "Generate new report"}
        </button>
      </div>
      {ai === "local" && (
        <p className="mt-1 text-[10px] text-slate-500">
          AI provider unavailable; showing template-based text when the model is not used.
        </p>
      )}
      {mode && (
        <p className="text-[10px] text-slate-500">Mode: {mode}</p>
      )}
      <div className="mt-2 flex-1 overflow-y-auto text-sm leading-relaxed text-slate-200">
        {text.split("\n\n").map((p, i) => (
          <p key={i} className="mb-2">
            {p}
          </p>
        ))}
      </div>
      <button
        type="button"
        onClick={printReport}
        className="mt-2 w-full rounded bg-blue-600 py-1.5 text-xs font-bold text-white"
      >
        Download report (print to PDF)
      </button>
    </div>
  );
}
