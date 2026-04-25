"use client";

import { useEffect, useState } from "react";
import { getHealth } from "@/lib/api";

export function DegradedModeBanner() {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    getHealth()
      .then((h) => {
        const parts: string[] = [];
        if (h.store === "local" && !h.store_fallback) {
          parts.push("Local SQLite store (no Supabase credentials or not selected).");
        }
        if (h.store_fallback) {
          parts.push(
            "Supabase was unavailable — fell back to local SQLite for this process"
          );
        }
        if (h.ai === "local") {
          parts.push(
            "Generative AI not configured (no OpenRouter key); incident text and NL search use templates and rules."
          );
        }
        setMsg(parts.length ? parts.join(" ") : null);
      })
      .catch(() => setMsg("Could not reach backend at configured API URL."));
  }, []);
  if (!msg) return null;
  return (
    <div className="mb-3 rounded border border-amber-600/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">
      {msg}
    </div>
  );
}
