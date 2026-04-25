import { Suspense } from "react";
import { DashboardClient } from "./dashboard-client";

export default function DashboardPage() {
  return (
    <Suspense
      fallback={
        <div className="text-slate-500">
          <p>Loading dashboard…</p>
        </div>
      }
    >
      <DashboardClient />
    </Suspense>
  );
}
