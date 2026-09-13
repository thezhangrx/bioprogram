// Interactive Scientific Discovery Report — 章节组件。
//
// 只消费 ReportData (Report Data Adapter 的产物); 不直接读文件, 不复制统计规则。
// 视觉: Scientific / minimal / information-dense; 交互用于比较/筛选/追溯, 不做动效炫技。

import { useMemo, useState } from "react";
import type { EvidenceCardData, KeyFinding, ReportData, SectionStatus, TableData } from "./types";
import { STATE_LABEL, fmt, fmtSigned, num } from "./ReportDataAdapter";
import { MarkdownViewer } from "../components/artifacts/MarkdownViewer";

export function SectionShell({ section, children, onFullscreen }: {
  section: SectionStatus; children: React.ReactNode; onFullscreen?: () => void;
}) {
  const tone: Record<string, string> = {
    completed: "bg-emerald-50 text-emerald-700 border-emerald-200",
    partial: "bg-amber-50 text-amber-700 border-amber-200",
    skipped: "bg-slate-50 text-slate-600 border-slate-200",
    unavailable: "bg-slate-50 text-slate-500 border-slate-200",
    not_selected: "bg-slate-50 text-slate-500 border-slate-200",
    pending: "bg-blue-50 text-blue-700 border-blue-200",
  };
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <header className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold text-slate-800">{section.title}</h2>
          <p className="mt-0.5 text-[11px] text-slate-500">{section.detail}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className={`rounded border px-2 py-0.5 text-[11px] ${tone[section.state]}`}>
            {STATE_LABEL[section.state]}
          </span>
          {onFullscreen && (
            <button onClick={onFullscreen}
                    className="rounded border border-slate-200 px-2 py-0.5 text-[11px] hover:bg-slate-50">
              Fullscreen
            </button>
          )}
        </div>
      </header>
      {children}
    </section>
  );
}

export function MetricCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded border border-slate-200 bg-slate-50/60 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-sm font-semibold text-slate-800">{value}</div>
      {hint && <div className="text-[10px] text-slate-500">{hint}</div>}
    </div>
  );
}

/** 带搜索/排序/列筛选的表格 (宽表允许横向滚动)。 */
export function DataTable({ table, initialSort, columns, pageSize = 25 }: {
  table: TableData; initialSort?: string; columns?: string[]; pageSize?: number;
}) {
  const cols = columns ?? table.columns;
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<string | null>(initialSort ?? null);
  const [filterCol, setFilterCol] = useState<string>("");
  const [filterVal, setFilterVal] = useState<string>("");
  const [page, setPage] = useState(0);

  const rows = useMemo(() => {
    let out = table.rows;
    if (q) {
      const needle = q.toLowerCase();
      out = out.filter((r) => cols.some((c) => String(r[c] ?? "").toLowerCase().includes(needle)));
    }
    if (filterCol && filterVal) {
      out = out.filter((r) => String(r[filterCol] ?? "") === filterVal);
    }
    if (sort) {
      out = [...out].sort((a, b) => {
        const av = num(a[sort]); const bv = num(b[sort]);
        if (av !== null && bv !== null) return bv - av;
        return String(b[sort] ?? "").localeCompare(String(a[sort] ?? ""));
      });
    }
    return out;
  }, [table.rows, cols, q, sort, filterCol, filterVal]);

  if (table.missing) {
    return <p className="text-[11px] text-slate-500">Unavailable: {table.path}</p>;
  }
  const values = filterCol
    ? Array.from(new Set(table.rows.map((r) => String(r[filterCol] ?? "")))).slice(0, 30)
    : [];
  const pages = Math.max(1, Math.ceil(rows.length / pageSize));
  const shown = rows.slice(page * pageSize, (page + 1) * pageSize);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <input value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }}
               placeholder="Search…"
               className="rounded border border-slate-200 px-2 py-1" />
        <select value={filterCol} onChange={(e) => { setFilterCol(e.target.value); setFilterVal(""); }}
                className="rounded border border-slate-200 px-2 py-1">
          <option value="">Filter column…</option>
          {cols.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        {filterCol && (
          <select value={filterVal} onChange={(e) => { setFilterVal(e.target.value); setPage(0); }}
                  className="rounded border border-slate-200 px-2 py-1">
            <option value="">any</option>
            {values.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
        )}
        <select value={sort ?? ""} onChange={(e) => setSort(e.target.value || null)}
                className="rounded border border-slate-200 px-2 py-1">
          <option value="">Sort…</option>
          {cols.map((c) => <option key={c} value={c}>sort by {c}</option>)}
        </select>
        <span className="text-slate-500">
          {rows.length} row(s){table.totalRows && table.totalRows > table.rows.length
            ? ` (artifact page of ${table.totalRows})` : ""}{table.truncated ? " · truncated" : ""}
        </span>
      </div>
      <div className="overflow-x-auto rounded border border-slate-200">
        <table className="min-w-full text-[11px]">
          <thead className="bg-slate-50 text-slate-600">
            <tr>{cols.map((c) => (
              <th key={c} className="whitespace-nowrap px-2 py-1 text-left font-medium">{c}</th>
            ))}</tr>
          </thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={i} className="border-t border-slate-100 hover:bg-slate-50/70">
                {cols.map((c) => (
                  <td key={c} className="whitespace-nowrap px-2 py-1 text-slate-700">
                    {String(r[c] ?? "")}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="flex items-center gap-2 text-[11px]">
          <button className="rounded border border-slate-200 px-2 py-0.5"
                  onClick={() => setPage((p) => Math.max(0, p - 1))}>prev</button>
          <span>{page + 1} / {pages}</span>
          <button className="rounded border border-slate-200 px-2 py-0.5"
                  onClick={() => setPage((p) => Math.min(pages - 1, p + 1))}>next</button>
        </div>
      )}
    </div>
  );
}

export function EvidenceCardView({ card, onOpenSource }: {
  card: EvidenceCardData; onOpenSource: (path: string) => void;
}) {
  const ci = card.ciLow !== null && card.ciHigh !== null
    ? `[${fmt(card.ciLow)}, ${fmt(card.ciHigh)}]` : "NA (bootstrap unavailable)";
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-slate-800">{card.feature}</h3>
        <span className="text-[11px] text-slate-500">{card.tier}</span>
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] text-slate-700">
        <div><dt className="text-slate-500">Overall ΔR²</dt><dd>{fmtSigned(card.effect)}</dd></div>
        <div><dt className="text-slate-500">95% CI</dt><dd>{ci}</dd></div>
        <div><dt className="text-slate-500">Coverage</dt><dd>{card.coverage}</dd></div>
        <div><dt className="text-slate-500">Direction concordance</dt>
          <dd>{fmt(card.concordance, 2)}</dd></div>
        <div><dt className="text-slate-500">Cell-line consistency</dt>
          <dd>{card.cellLineConsistency}</dd></div>
        <div><dt className="text-slate-500">Permutation FDR</dt>
          <dd>{fmt(card.permutationFdr)}</dd></div>
      </dl>
      <p className="mt-2 text-[11px] text-slate-500">Supported by: {card.models.join(" · ") || "NA"}</p>
      <button onClick={() => onOpenSource(card.source)}
              className="mt-2 rounded border border-slate-200 px-2 py-0.5 text-[11px] hover:bg-slate-50">
        View source
      </button>
    </div>
  );
}

export function FindingCard({ finding, onOpen, onSource }: {
  finding: KeyFinding; onOpen: (sectionId: string) => void; onSource: (path: string) => void;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-medium text-slate-800">{finding.headline}</h3>
        {finding.strength && (
          <span className="shrink-0 rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-[10px] text-slate-600">
            {finding.strength}
          </span>
        )}
      </div>
      <p className="mt-1 text-[11px] text-slate-600">{finding.detail}</p>
      <div className="mt-2 grid grid-cols-2 gap-2 md:grid-cols-4">
        {finding.metrics.map((m) => (
          <MetricCard key={m.label} label={m.label} value={m.value} />
        ))}
      </div>
      <div className="mt-2 flex gap-2 text-[11px]">
        <button className="rounded border border-slate-200 px-2 py-0.5 hover:bg-slate-50"
                onClick={() => onOpen(finding.section)}>View analysis</button>
        {finding.sources[0] && (
          <button className="rounded border border-slate-200 px-2 py-0.5 hover:bg-slate-50"
                  onClick={() => onSource(finding.sources[0])}>View source</button>
        )}
      </div>
    </div>
  );
}

export function OverviewSection({ data }: { data: ReportData }) {
  return (
    <div className="space-y-3">
      <div className="grid gap-2 md:grid-cols-3">
        {data.scope.slice(0, 9).map((s) => (
          <MetricCard key={s.label} label={s.label} value={s.value}
                      hint={s.included === undefined ? undefined : s.included ? "included" : "not included"} />
        ))}
      </div>
      <h3 className="text-xs font-semibold text-slate-700">Key findings</h3>
      <p className="text-[11px] text-slate-500">
        Findings are derived from backend artifacts (evidence tier, ΔR², CI, enrichment FDR).
        Association only — no causal claim.
      </p>
    </div>
  );
}

export function DatasetSection({ data }: { data: ReportData }) {
  const warn = (data.markdown.anomaly ?? "").split("\n").filter((l) => l.startsWith("- ")).slice(0, 6);
  return (
    <div className="space-y-3">
      <div className="grid gap-2 md:grid-cols-3">
        {data.scope.filter((s) => ["experiment count", "valid experiments", "models",
          "cell lines", "splits", "environments"].includes(s.label)).map((s) => (
          <MetricCard key={s.label} label={s.label} value={s.value} />
        ))}
      </div>
      {warn.length > 0 && (
        <div className="rounded border border-amber-200 bg-amber-50 p-2 text-[11px] text-amber-800">
          <div className="font-medium">QC warnings surfaced from artifacts</div>
          <ul className="mt-1 list-disc pl-4">{warn.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </div>
      )}
      <div className="max-h-72 overflow-y-auto rounded border border-slate-200 p-2">
        <MarkdownViewer path="summary/01_data_quality.md" />
      </div>
    </div>
  );
}

export function PredictionSection({ data }: { data: ReportData }) {
  return (
    <div className="space-y-3">
      <DataTable table={data.tables.prediction} initialSort="R2" />
      <p className="text-[11px] text-slate-500">
        Generalization by cell line / LOCO is reported separately from factor-discovery evidence.
      </p>
      <DataTable table={data.tables.loco} columns={
        data.tables.loco.columns.slice(0, Math.min(8, data.tables.loco.columns.length))} />
    </div>
  );
}

export function EnvironmentSection({ data }: { data: ReportData }) {
  return (
    <div className="space-y-4">
      <div className="grid gap-2 md:grid-cols-2">
        {data.evidenceCards.map((c) => (
          <EvidenceCardView key={c.feature} card={c}
                            onOpenSource={() => undefined} />
        ))}
      </div>
      <h3 className="text-xs font-semibold text-slate-700">Conditional ΔR² (paired baseline)</h3>
      <DataTable table={data.tables.conditional} initialSort="delta_r2_mean" />
      <h3 className="text-xs font-semibold text-slate-700">Main effects</h3>
      <DataTable table={data.tables.mainEffects} initialSort="main_r2_delta" />
      <h3 className="text-xs font-semibold text-slate-700">Bootstrap CI (ΔR²)</h3>
      <DataTable table={data.tables.bootstrap} initialSort="estimate" />
      <h3 className="text-xs font-semibold text-slate-700">Permutation tests (null hypothesis per row)</h3>
      <DataTable table={data.tables.permutation} initialSort="p_value" />
      <h3 className="text-xs font-semibold text-slate-700">Factorial ANOVA</h3>
      {data.tables.anova.missing
        ? <p className="text-[11px] text-slate-500">Not selected in Analysis Plan or unavailable.</p>
        : <DataTable table={data.tables.anova} initialSort="p_value" />}
      <h3 className="text-xs font-semibold text-slate-700">Interactions</h3>
      <p className="text-[11px] text-slate-500">
        Interaction analysis is optional ({String(data.plan?.environment
          ? JSON.stringify((data.plan?.environment as Record<string, unknown>).interaction)
          : "n/a")} in plan); per-pair results appear in the permutation table.
      </p>
    </div>
  );
}

export function SequenceSection({ data }: { data: ReportData }) {
  const motifs = data.tables.motifs;
  return (
    <div className="space-y-3">
      {motifs.missing
        ? <p className="text-[11px] text-slate-500">
            Unavailable: no compatible sequence attribution artifact (CNN ISM/IG or Transformer IG).
          </p>
        : (
          <>
            <DataTable table={motifs} initialSort="support_count" />
            <h3 className="text-xs font-semibold text-slate-700">Motif enrichment (Fisher + BH-FDR)</h3>
            <DataTable table={data.tables.motifEnrichment} initialSort="FDR" />
            <h3 className="text-xs font-semibold text-slate-700">Cross-model / cross-kernel consistency</h3>
            <DataTable table={data.tables.motifConsistency} columns={
              ["motif_id", "comparison_type", "group", "n_supporting", "n_total",
                "supporting_members", "status", "reason"]} />
          </>
        )}
      <h3 className="text-xs font-semibold text-slate-700">Position attribution</h3>
      <DataTable table={data.tables.attribution} columns={
        ["feature", "channel", "position", "model", "architecture", "split_type",
          "cell_line", "environment", "method", "importance", "snr"]} />
      <p className="text-[11px] text-slate-500">
        SHAP / IG / ISM / attention are attribution or mutation effects — not statistical significance.
      </p>
    </div>
  );
}

export function CelllineSection({ data }: { data: ReportData }) {
  const labels = useMemo(() => {
    const set = new Set<string>();
    for (const r of data.tables.cellline.rows) set.add(String(r.context_label ?? ""));
    return Array.from(set).filter(Boolean);
  }, [data.tables.cellline.rows]);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2 text-[11px]">
        {labels.map((l) => (
          <span key={l} className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5">{l}</span>
        ))}
      </div>
      <DataTable table={data.tables.cellline} initialSort="heterogeneity" />
      <p className="text-[11px] text-slate-500">
        Labels come from the backend (direction + magnitude heterogeneity + CI overlap);
        cell-line differences are not interpreted as different mechanisms.
      </p>
    </div>
  );
}

export function EvidenceSection({ data, onOpenSource }: {
  data: ReportData; onOpenSource: (p: string) => void;
}) {
  const [tier, setTier] = useState("");
  const tiers = Array.from(new Set(data.evidenceCards.map((c) => c.tier))).filter(Boolean);
  const cards = tier ? data.evidenceCards.filter((c) => c.tier === tier) : data.evidenceCards;
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <select value={tier} onChange={(e) => setTier(e.target.value)}
                className="rounded border border-slate-200 px-2 py-1">
          <option value="">All evidence tiers</option>
          {tiers.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <span className="text-slate-500">{cards.length} feature(s)</span>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {cards.map((c) => (
          <EvidenceCardView key={c.feature} card={c} onOpenSource={onOpenSource} />
        ))}
      </div>
      <h3 className="text-xs font-semibold text-slate-700">Evidence matrix (interactive)</h3>
      <DataTable table={data.tables.evidence} initialSort="coverage" />
      <h3 className="text-xs font-semibold text-slate-700">Effect vs attribution (Importance–ΔR²)</h3>
      <DataTable table={data.tables.importance} initialSort="delta_r2" />
    </div>
  );
}

export function HypothesisSection({ data }: { data: ReportData }) {
  return (
    <div className="space-y-3">
      <p className="text-[11px] text-slate-500">
        Hypotheses are phrased as testable candidates (associated with / suggests / candidate factor);
        causal wording requires backend-produced causal evidence.
      </p>
      <div className="max-h-[520px] overflow-y-auto rounded border border-slate-200 p-3">
        <MarkdownViewer path="summary/07_biological_hypotheses.md" />
      </div>
    </div>
  );
}

export function ProvenanceSection({ data }: { data: ReportData }) {
  return (
    <div className="space-y-3">
      <dl className="grid gap-x-6 gap-y-1 text-[11px] md:grid-cols-2">
        {data.provenance.map((p) => (
          <div key={p.label} className="flex justify-between gap-3 border-b border-slate-100 py-0.5">
            <dt className="text-slate-500">{p.label}</dt>
            <dd className="truncate text-slate-800" title={p.value}>{p.value || "NA"}</dd>
          </div>
        ))}
      </dl>
      <h3 className="text-xs font-semibold text-slate-700">Analysis tasks (status / artifact)</h3>
      <DataTable table={{
        path: "analysis_status.json", columns: ["taskId", "selected", "available", "status",
          "reason", "artifact"],
        rows: data.tasks.map((t) => ({
          taskId: t.taskId, selected: String(t.selected), available: String(t.available),
          status: t.status, reason: t.reason, artifact: t.artifact,
        })),
      }} />
      {data.warnings.length > 0 && (
        <div className="rounded border border-slate-200 bg-slate-50 p-2 text-[11px] text-slate-600">
          Missing artifacts: {data.warnings.join(", ")}
        </div>
      )}
    </div>
  );
}
