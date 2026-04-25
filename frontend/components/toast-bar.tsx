"use client";

export function ToastBar({
  message,
  kind = "error",
  onClose,
}: {
  message: string;
  kind?: "error" | "success" | "info";
  onClose: () => void;
}) {
  const cls =
    kind === "error"
      ? "border-rose-800 bg-rose-950/90 text-rose-100"
      : kind === "success"
        ? "border-emerald-800 bg-emerald-950/90 text-emerald-100"
        : "border-slate-600 bg-slate-900/95 text-slate-200";
  return (
    <div
      className={`fixed bottom-4 right-4 z-50 flex max-w-sm items-center gap-2 rounded border px-3 py-2 text-sm shadow-lg ${cls}`}
      role="status"
    >
      <span className="flex-1">{message}</span>
      <button
        type="button"
        onClick={onClose}
        className="text-xs opacity-70 hover:opacity-100"
      >
        Dismiss
      </button>
    </div>
  );
}
