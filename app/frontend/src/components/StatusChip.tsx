import type { StageStatus } from "../types";

const MAP: Record<StageStatus, { label: string; cls: string }> = {
  completed: { label: "已完成", cls: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  running: { label: "运行中", cls: "bg-blue-50 text-blue-700 ring-blue-200" },
  failed: { label: "失败", cls: "bg-red-50 text-red-700 ring-red-200" },
  pending: { label: "待处理", cls: "bg-slate-100 text-slate-500 ring-slate-200" },
  skipped: { label: "已跳过", cls: "bg-slate-100 text-slate-400 ring-slate-200" },
  unavailable: { label: "不可用", cls: "bg-slate-100 text-slate-400 ring-slate-200" },
  warning: { label: "需复核", cls: "bg-amber-50 text-amber-700 ring-amber-200" },
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
