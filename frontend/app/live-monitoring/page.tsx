import { Suspense } from "react";
import { LiveMonitoringClient } from "@/components/live-monitoring-client";

export default function LiveMonitoringPage() {
  return (
    <Suspense
      fallback={
        <div className="text-slate-500">
          <p>Loading…</p>
        </div>
      }
    >
      <LiveMonitoringClient />
    </Suspense>
  );
}
