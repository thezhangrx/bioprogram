import type { StageStatus } from "../types";

const MAP: Record<StageStatus, { label: string; cls: string }> = {
  completed: { label: "Completed", cls: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  running: { label: "Running", cls: "bg-blue-50 text-blue-700 ring-blue-200" },
  failed: { label: "Failed", cls: "bg-red-50 text-red-700 ring-red-200" },
  pending: { label: "Pending", cls: "bg-slate-100 text-slate-500 ring-slate-200" },
  skipped: { label: "Skipped", cls: "bg-slate-100 text-slate-400 ring-slate-200" },
  unavailable: { label: "Unavailable", cls: "bg-slate-100 text-slate-400 ring-slate-200" },
  warning: { label: "Review", cls: "bg-amber-50 text-amber-700 ring-amber-200" },
};

export function StatusChip({ status }: { status: StageStatus }) {
  const m = MAP[status] ?? MAP.pending;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${m.cls}`}>
      <span className="size-1.5 rounded-full bg-current" />
      {m.label}
    </span>
  );
}
