"use client";

import { useState } from "react";

export function AddWidgetButton() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rounded border border-slate-600 bg-slate-800/80 px-2 py-1 text-slate-200 hover:bg-slate-800"
      >
        + Add widget
      </button>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm rounded border border-avline bg-avbg p-4 shadow-xl">
            <h3 className="text-sm font-medium text-slate-100">Add widget</h3>
            <p className="mt-2 text-xs text-slate-500">
              Custom dashboard widgets (extra charts, notes, or links) are not wired in this
              hackathon build. Add them by extending the dashboard page or your design system
              components.
            </p>
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="mt-4 w-full rounded bg-blue-600 py-1.5 text-xs font-semibold text-white"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </>
  );
}
