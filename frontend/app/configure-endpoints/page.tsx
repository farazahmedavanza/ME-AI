import { Suspense } from "react";
import { ConfigureEndpointsClient } from "@/components/configure-endpoints-client";

export default function ConfigureEndpointsPage() {
  return (
    <Suspense
      fallback={
        <div className="text-slate-500">
          <p>Loading…</p>
        </div>
      }
    >
      <ConfigureEndpointsClient />
    </Suspense>
  );
}
