"use client";

import { useState } from "react";
import { apiPost } from "@/lib/api";

const MAROON = "#ffffff";
const FOOTER_GREY = "#6b7280";

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function buildPrintHtml(body: string, logoSrc: string, dateStr: string): string {
  const paragraphs = body
    .split(/\n\n+/)
    .map((p) => p.trim())
    .filter(Boolean)
    .map((p) => `<p class="body-p">${escapeHtml(p)}</p>`)
    .join("");
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Incident report</title>
<style>
  * { box-sizing: border-box; }
  @page { margin: 12mm; }
  body { margin: 0; font-family: system-ui, -apple-system, Segoe UI, sans-serif; color: #1f2937; font-size: 12pt; line-height: 1.5; }
  .header-row { display: flex; align-items: flex-start; justify-content: space-between; padding-bottom: 12px; border-bottom: 2px solid ${MAROON}; }
  .header-title { text-align: right; }
  .header-title h1 { margin: 0; font-size: 18pt; font-weight: 700; color: ${MAROON}; }
  .header-title .date { margin-top: 6px; font-size: 11pt; color: #374151; }
  .logo { height: 40px; width: auto; object-fit: contain; display: block; }
  .main { margin-top: 20px; }
  .body-p { margin: 0 0 12px; text-align: justify; }
  .footer-wrap { margin-top: 32px; padding-top: 12px; border-top: 2px solid ${MAROON}; }
  .footer { display: flex; justify-content: space-between; align-items: center; font-size: 8pt; color: ${FOOTER_GREY}; flex-wrap: wrap; gap: 8px; }
  .footer-center { flex: 1; text-align: center; min-width: 80px; }
  .footer-left { text-align: left; }
  .footer-right { text-align: right; }
</style>
</head>
<body>
  <div class="header-row">
    <div><img class="logo" src="${logoSrc}" alt="Avanza Solutions" /></div>
    <div class="header-title">
      <h1>Incident report</h1>
      <div class="date">Date: ${escapeHtml(dateStr)}</div>
    </div>
  </div>
  <div class="main">${paragraphs || `<p class="body-p">&mdash;</p>`}</div>
  <div class="footer-wrap">
    <div class="footer">
      <span class="footer-left">© 2026 Avanza Solutions. Powered by ME Ai</span>
      <span class="footer-center">Confidential</span>
      <span class="footer-right">Page 1</span>
    </div>
  </div>
</body>
</html>`;
}

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
    const logoSrc = new URL("/Avanza-logo.png", window.location.origin).href;
    const dateStr = new Date().toLocaleDateString("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
    w.document.write(buildPrintHtml(text, logoSrc, dateStr));
    w.document.close();
    w.print();
  }

  return (
    <div className="flex h-full min-h-[240px] flex-col overflow-hidden rounded border border-avline bg-slate-900/30 p-2">
      <div
        className="flex items-center justify-between border-b-2 pb-2"
        style={{ borderColor: MAROON }}
      >
        <div className="text-sm font-semibold" style={{ color: MAROON }}>
          AI Incident report
        </div>
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
      {mode && <p className="text-[10px] text-slate-500">Mode: {mode}</p>}
      <div className="mt-2 flex-1 overflow-y-auto text-sm leading-relaxed text-slate-200">
        {text.split("\n\n").map((p, i) => (
          <p key={i} className="mb-2 text-justify last:mb-0">
            {p}
          </p>
        ))}
      </div>
      <div
        className="mt-3 border-t-2 pt-2 text-center text-[10px] text-slate-500"
        style={{ borderColor: MAROON }}
      >
        Confidential — © 2026 Avanza Solutions
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
