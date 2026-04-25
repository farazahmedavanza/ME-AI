"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { LogUpload } from "@/components/log-upload";

export default function UploadPage() {
  const router = useRouter();
  return (
    <div className="mx-auto max-w-lg p-6">
      <div className="mb-1 text-lg font-light text-white">avanza</div>
      <div className="mb-6 text-xs font-bold uppercase text-blue-500">BANKING</div>
      <h1 className="text-lg font-medium text-slate-200">Upload API logs</h1>
      <p className="mt-1 text-sm text-slate-500">
        JSON array of log objects (see <code className="text-slate-400">backend/data/api_logs.json</code>).
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
