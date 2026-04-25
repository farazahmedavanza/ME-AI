"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { AvanzaBrandLogo } from "@/components/avanza-brand-logo";
import { cn } from "@/lib/cn";

const nav = [
  { href: "/dashboard", label: "Overview" },
  { href: "/live-monitoring", label: "Live Monitoring" },
  { href: "/upload", label: "Upload logs" },
  { href: "/dashboard#apis", label: "APIs" },
  { href: "/dashboard#alerts", label: "Alerts" },
  { href: "/dashboard#incident", label: "Incident reports" },
  { href: "/dashboard#search", label: "Log search (AI)" },
  { href: "/dashboard#analytics", label: "Analytics" },
  { href: "/dashboard#sla", label: "SLA & policies" },
  { href: "/dashboard#jobs", label: "Jobs monitor" },
  { href: "/dashboard#settings", label: "Settings" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  return (
    <div className="flex min-h-screen">
      <aside className="w-56 shrink-0 border-r border-avline bg-slate-950/80 p-3">
        <div className="px-1 py-2">
          <Link href="/dashboard" className="block outline-offset-2 hover:opacity-90">
            <AvanzaBrandLogo size="md" />
          </Link>
        </div>
        <nav className="mt-2 space-y-0.5">
          {nav.map((n) => {
            const base = n.href.split("#")[0];
            const active =
              path === n.href ||
              (path === base && n.label === "Overview" && base === "/dashboard") ||
              (n.label === "Live Monitoring" &&
                (path === "/live-monitoring" || path === "/configure-endpoints"));
            return (
            <Link
              key={n.href}
              href={n.href}
              className={cn(
                "block rounded px-2 py-1.5 text-sm text-slate-400 hover:bg-slate-900 hover:text-slate-100",
                active && "bg-slate-900 text-slate-100"
              )}
            >
              {n.label}
            </Link>
            );
          })}
        </nav>
        <div className="mt-8 border-t border-avline pt-3 text-xs text-slate-500">
          <div className="font-medium text-slate-300">Ops team</div>
          <div>Command center</div>
        </div>
      </aside>
      <div className="min-w-0 flex-1 p-4 md:p-6">{children}</div>
    </div>
  );
}
