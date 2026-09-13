// Standalone QC Dashboard: 只读渲染 data_QC 引擎的 qc_summary (qc_summary.json)。
import type { QcSession } from "../types";
import { artifactApi } from "../api/artifacts";

function num(obj: Record<string, unknown>, ...keys: string[]): number | null {
  let node: unknown = obj;
  for (const k of keys) {
    if (node && typeof node === "object" && k in (node as Record<string, unknown>)) {
      node = (node as Record<string, unknown>)[k];
    } else return null;
  }
  return typeof node === "number" ? node : null;
}

function overall(sum: Record<string, unknown>): { label: string; cls: string } {
  const amb = num(sum, "ambiguous_bases", "n_affected_sequences") ?? 0;
  const out = num(sum, "outliers", "n_outliers") ?? 0;
  if ((amb ?? 0) > 0 || (out ?? 0) > 0) {
    return { label: "🟡 Review recommended", cls: "text-amber-700" };
  }
  const pass = sum["qc_pass"];
  if (pass === false) return { label: "🔴 Major issues detected", cls: "text-red-600" };
  if (pass === true) return { label: "🟢 Good", cls: "text-emerald-600" };
  return { label: "Completed — review details below", cls: "text-slate-600" };
}

export function QcDashboard({ session }: { session: QcSession }) {
  const s = (session.qc_summary ?? {}) as Record<string, unknown>;
  const o = overall(s);
  const sizeObj = s["sample_size"] as Record<string, unknown> | undefined;
  const perCell = (sizeObj?.["per_cell_line"] ?? null) as Record<string, unknown> | null;
  const cellsCount = perCell ? Object.keys(perCell).length : null;
  const figures = session.figures ?? [];
  const reportPath = session.outputs?.report;
  const cards: { k: string; v: string }[] = [
    { k: "Samples", v: String(num(s, "sample_size", "total_samples") ?? "—") },
    { k: "Cell lines", v: cellsCount != null ? String(cellsCount) : "—" },
    { k: "Sequence length", v: String(num(s, "length_consistency", "recommended_length_L") ?? "—") },
    { k: "Ambiguous samples", v: String(num(s, "ambiguous_bases", "n_affected_sequences") ?? 0) },
    { k: "Outliers", v: String(num(s, "outliers", "n_outliers") ?? 0) },
    { k: "Overall", v: o.label },
  ];
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-6">
        {cards.map((c) => (
          <div key={c.k} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
            <p className="text-[10px] uppercase tracking-wide text-slate-400">{c.k}</p>
            <p className={`mt-0.5 truncate text-sm font-semibold ${c.k === "Overall" ? o.cls : "text-slate-700"}`}>{c.v}</p>
          </div>
        ))}
      </div>
      {figures.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-2">
          {figures.map((f) => (
            <figure key={f} className="overflow-hidden rounded-lg border border-slate-200">
              <img src={artifactApi.rawUrl(f)} alt={f.split("/").pop()} className="max-h-64 w-full object-contain bg-white" />
              <figcaption className="border-t border-slate-100 bg-slate-50 px-2 py-1 text-[10px] text-slate-500">{f.split("/").pop()}</figcaption>
            </figure>
          ))}
        </div>
      )}
      <p className="text-[11px] text-slate-400">
        说明：本页是“数据体检”，只读检测与报告；不修改数据、不推断模型表现。Overall 仅表示数据质量概览。
      </p>
      {reportPath && (
        <a href={artifactApi.rawUrl(reportPath)} download
           className="inline-block rounded-md border border-slate-300 px-3 py-1 text-xs hover:bg-slate-50">
          ⬇ Export Report (quality_report.md)
        </a>
      )}
    </div>
  );
}
