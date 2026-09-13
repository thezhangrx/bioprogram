// Interactive Scientific Discovery Report — 报告外壳。
//
// 结构: Scientific Engines -> Artifacts -> Report Data Adapter -> Report Sections。
// 交互: 章节导航 / Key Findings drill-down / artifact viewer / fullscreen / print (PDF)。
// 不重新训练, 不需要 GPU, 不重算任何统计量。

import { useEffect, useMemo, useRef, useState } from "react";
import { buildReportData, httpDeps, STATE_LABEL } from "./ReportDataAdapter";
import {
  CelllineSection, DatasetSection, EnvironmentSection, EvidenceSection, FindingCard,
  HypothesisSection, OverviewSection, PredictionSection, ProvenanceSection, SectionShell,
  SequenceSection,
} from "./sections";
import type { ReportData, ReportSectionId } from "./types";
import { ArtifactViewer } from "../components/artifacts/ArtifactViewer";

const ORDER: ReportSectionId[] = ["overview", "dataset", "prediction", "environment",
  "sequence", "cellline", "evidence", "hypotheses", "provenance"];

const RAW_MD: Partial<Record<ReportSectionId, string>> = {
  dataset: "summary/01_data_quality.md",
  prediction: "summary/02_prediction_generalization.md",
  environment: "summary/03_environment_effects.md",
  sequence: "summary/04_sequence_and_motifs.md",
  cellline: "summary/05_cellline_heterogeneity.md",
  evidence: "summary/06_evidence_integration.md",
  hypotheses: "summary/07_biological_hypotheses.md",
};

export function ScientificReport({ outputDir }: { outputDir: string | null }) {
  const [data, setData] = useState<ReportData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState<ReportSectionId>("overview");
  const [fullscreen, setFullscreen] = useState<ReportSectionId | null>(null);
  const [sourcePath, setSourcePath] = useState<string | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setData(null); setError(null);
    if (!outputDir) return;
    let cancelled = false;
    buildReportData(outputDir, httpDeps())
      .then((d) => { if (!cancelled) setData(d); })
      .catch((e) => { if (!cancelled) setError(String(e)); });
    return () => { cancelled = true; };
  }, [outputDir]);

  const sectionById = useMemo(() => {
    const map = new Map<ReportSectionId, ReportData["sections"][number]>();
    for (const s of data?.sections ?? []) map.set(s.id, s);
    return map;
  }, [data]);

  if (!outputDir) {
    return <p className="text-xs text-slate-400">分析运行完成后生成报告（Analysis 阶段）。</p>;
  }
  if (error) return <p className="text-xs text-red-600">Report data error: {error}</p>;
  if (!data) return <p className="text-xs text-slate-400">Assembling report from artifacts…</p>;

  const openSource = (path: string) => {
    if (!path) return;
    setSourcePath(path);
  };

  const renderSection = (id: ReportSectionId) => {
    const section = sectionById.get(id);
    if (!section) return null;
    const onFullscreen = () => setFullscreen(id);
    const body = (() => {
      switch (id) {
        case "overview": return <OverviewSection data={data} />;
        case "dataset": return <DatasetSection data={data} />;
        case "prediction": return <PredictionSection data={data} />;
        case "environment": return <EnvironmentSection data={data} />;
        case "sequence": return <SequenceSection data={data} />;
        case "cellline": return <CelllineSection data={data} />;
        case "evidence": return <EvidenceSection data={data} onOpenSource={openSource} />;
        case "hypotheses": return <HypothesisSection data={data} />;
        case "provenance": return <ProvenanceSection data={data} />;
      }
    })();
    return (
      <SectionShell section={section} onFullscreen={onFullscreen}>
        {body}
        {RAW_MD[id] && (
          <div className="mt-3 flex items-center gap-2 text-[11px]">
            <button className="rounded border border-slate-200 px-2 py-0.5 hover:bg-slate-50"
                    onClick={() => setShowRaw((v) => !v)}>
              {showRaw ? "Hide" : "Show"} source markdown
            </button>
            <button className="rounded border border-slate-200 px-2 py-0.5 hover:bg-slate-50"
                    onClick={() => openSource(RAW_MD[id] as string)}>Open in viewer</button>
          </div>
        )}
        {showRaw && RAW_MD[id] && (
          <div className="mt-2 max-h-64 overflow-y-auto rounded border border-slate-200 p-2">
            <pre className="whitespace-pre-wrap text-[10px] text-slate-600">
              {markdownFor(data, id)}
            </pre>
          </div>
        )}
      </SectionShell>
    );
  };

  return (
    <div className="space-y-3" ref={containerRef}>
      <header className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white p-3">
        <div>
          <h1 className="text-sm font-semibold text-slate-800">
            Interactive Scientific Discovery Report
          </h1>
          <p className="text-[11px] text-slate-500">
            Dataset → Quality → Prediction → Factor effects → Sequence patterns → Cell-line context
            → Evidence → Hypotheses → Source artifacts. Read-only; no retraining.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[11px]">
          <button className="rounded border border-slate-200 px-2 py-1 hover:bg-slate-50"
                  onClick={() => window.print()}>Print / PDF</button>
          <button className="rounded border border-slate-200 px-2 py-1 hover:bg-slate-50"
                  onClick={() => exportHtml(containerRef.current)}>Export HTML</button>
        </div>
      </header>

      <nav className="flex flex-wrap gap-1 text-[11px]">
        {ORDER.map((id) => {
          const s = sectionById.get(id);
          return (
            <button key={id} onClick={() => setActive(id)}
                    className={`rounded border px-2 py-1 ${active === id
                      ? "border-blue-300 bg-blue-50 text-blue-700" : "border-slate-200 hover:bg-slate-50"}`}>
              {s?.title ?? id}
              <span className="ml-1 text-slate-400">{s ? STATE_LABEL[s.state] : ""}</span>
            </button>
          );
        })}
      </nav>

      <div className="grid gap-3 lg:grid-cols-[1fr_300px]">
        <div className="space-y-3">
          {active === "overview" && (
            <div className="space-y-2">
              {data.findings.length === 0
                ? <p className="rounded border border-slate-200 bg-white p-3 text-[11px] text-slate-500">
                    No finding passed the backend evidence rules in this batch (nothing is fabricated).
                  </p>
                : data.findings.map((f) => (
                  <FindingCard key={f.id} finding={f}
                               onOpen={(sid) => setActive(sid as ReportSectionId)}
                               onSource={openSource} />
                ))}
            </div>
          )}
          {renderSection(active)}
        </div>

        <aside className="space-y-3">
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <h3 className="text-xs font-semibold text-slate-700">Evidence cards</h3>
            <ul className="mt-1 space-y-1 text-[11px]">
              {data.evidenceCards.map((c) => (
                <li key={c.feature}>
                  <button className="w-full text-left hover:text-blue-700"
                          onClick={() => { setActive("evidence"); }}>
                    <span className="font-medium">{c.feature}</span>
                    <span className="ml-1 text-slate-500">{c.tier}</span>
                  </button>
                </li>
              ))}
              {data.evidenceCards.length === 0 && <li className="text-slate-400">(none)</li>}
            </ul>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-3">
            <h3 className="text-xs font-semibold text-slate-700">Figures</h3>
            <ul className="mt-1 max-h-64 space-y-1 overflow-y-auto text-[11px]">
              {data.figures.slice(0, 60).map((f) => (
                <li key={f.path}>
                  <button className="w-full truncate text-left hover:text-blue-700"
                          onClick={() => openSource(f.path)}>{f.name}</button>
                </li>
              ))}
            </ul>
          </div>
          <div className="rounded-lg border border-slate-200 bg-white p-3 text-[11px]">
            <h3 className="text-xs font-semibold text-slate-700">Analysis scope</h3>
            <ul className="mt-1 space-y-0.5">
              {data.scope.slice(0, 14).map((s) => (
                <li key={s.label} className="flex justify-between gap-2">
                  <span className="text-slate-500">{s.label}</span>
                  <span className={s.included === false ? "text-slate-400" : "text-slate-700"}>
                    {s.included === undefined ? s.value : s.included ? "✓ Included" : "Not selected"}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>

      {fullscreen && (
        <div className="fixed inset-0 z-50 overflow-auto bg-white p-4">
          <div className="mb-2 flex justify-end">
            <button className="rounded border border-slate-200 px-2 py-1 text-[11px]"
                    onClick={() => setFullscreen(null)}>Exit fullscreen</button>
          </div>
          {renderSection(fullscreen)}
        </div>
      )}

      {sourcePath && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/20">
          <div className="h-full w-[min(900px,90vw)] overflow-y-auto bg-white p-4 shadow-xl">
            <div className="mb-2 flex items-center justify-between">
              <span className="truncate text-xs text-slate-600">{sourcePath}</span>
              <button className="rounded border border-slate-200 px-2 py-0.5 text-[11px]"
                      onClick={() => setSourcePath(null)}>Close</button>
            </div>
            <ArtifactViewer path={sourcePath}
                            kind={sourcePath.endsWith(".md") ? "md" : "csv"} />
          </div>
        </div>
      )}
    </div>
  );
}

const MD_KEYS: Partial<Record<ReportSectionId, string>> = {
  dataset: "dataQuality", prediction: "prediction", environment: "environment",
  sequence: "sequenceMotifs", cellline: "cellline", evidence: "evidence",
  hypotheses: "hypotheses",
};

function markdownFor(data: ReportData, id: ReportSectionId): string {
  const key = MD_KEYS[id];
  return key ? (data.markdown[key] ?? "") : "";
}

function exportHtml(node: HTMLElement | null) {
  if (!node) return;
  const html = `<!doctype html><html><head><meta charset="utf-8">`
    + `<title>Interactive Scientific Discovery Report</title>`
    + `<style>body{font-family:system-ui,sans-serif;margin:24px;color:#0f172a}`
    + `table{border-collapse:collapse;font-size:11px}td,th{border:1px solid #e2e8f0;padding:2px 6px}`
    + `.rounded{border:1px solid #e2e8f0;border-radius:6px;padding:8px;margin:6px 0}</style></head><body>`
    + `<p><em>Static snapshot exported from the interactive report (HTML). `
    + `Interactive drill-down lives in the web version.</em></p>`
    + node.innerHTML + `</body></html>`;
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "scientific_discovery_report.html";
  a.click();
  URL.revokeObjectURL(url);
}
