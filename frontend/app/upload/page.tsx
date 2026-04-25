"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { AvanzaBrandLogo } from "@/components/avanza-brand-logo";
import { LogUpload } from "@/components/log-upload";

export default function UploadPage() {
  const router = useRouter();
  return (
    <div className="mx-auto max-w-lg p-6">
      <div className="mb-6">
        <AvanzaBrandLogo size="md" />
      </div>
      <h1 className="text-lg font-medium text-slate-200">Upload API logs</h1>
      <p className="mt-1 text-sm text-slate-500">
        Upload a <span className="text-slate-300">JSON array</span> of log objects, or a{" "}
        <span className="text-slate-300">text / Rdv / .log</span> file (see{" "}
        <code className="text-slate-400">backend/data/api_logs.json</code> for JSON shape).
      </p>
      <div className="mt-4">
        <LogUpload
          onDone={() => {
            router.push("/dashboard");
            router.refresh();
          }}
        />
      </div>
      <p className="mt-4 text-sm">
        <Link href="/dashboard" className="text-blue-400 hover:underline">
          ← Back to dashboard
        </Link>
      </p>
    </div>
  );
}
