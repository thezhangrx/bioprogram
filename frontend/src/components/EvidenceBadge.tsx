// EvidenceBadge: 只负责把后端已给出的 evidence 字段渲染成统一 Badge;
// 不做任何 SNR/FDR 阈值判定。
import type { ReactNode } from "react";

const RULES: { rx: RegExp; label: string; cls: string }[] = [
  { rx: /strong/i, label: "Strong convergent evidence", cls: "bg-emerald-50 text-emerald-700 ring-emerald-200" },
  { rx: /moderate/i, label: "Moderate convergent evidence", cls: "bg-amber-50 text-amber-700 ring-amber-200" },
  { rx: /model-specific|exploratory/i, label: "Model-specific / exploratory", cls: "bg-blue-50 text-blue-700 ring-blue-200" },
  { rx: /inconclusive/i, label: "Inconclusive", cls: "bg-slate-100 text-slate-500 ring-slate-200" },
];

export function evidenceBadge(value: string): ReactNode {
  const v = String(value).trim();
  const hit = RULES.find((r) => r.rx.test(v));
  if (hit) {
    return (
      <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium ring-1 ${hit.cls}`}>
        <span className="size-1.5 rounded-full bg-current" /> {hit.label}
      </span>
    );
  }
  // 无匹配: 原样显示 (不加星号体系)
  return <span className="text-slate-600">{v || "—"}</span>;
}
