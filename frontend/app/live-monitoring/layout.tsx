import type { Metadata } from "next";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "Live Monitoring | API Health & SLA Monitor",
  description: "HTTP endpoint monitors, alerts, and configuration",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
