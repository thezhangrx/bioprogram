import { useEffect, useState } from "react";
import { analysisApiOutputs, type AnalysisOutputEntry } from "../api/analysis";
import { MarkdownViewer } from "./artifacts/MarkdownViewer";
import { ScientificReport } from "../reports/ScientificReport";

type Mode = "report" | "raw";

export function ReportsPanel({ outputDir }: { outputDir: string | null }) {
  const [mode, setMode] = useState<Mode>("report");
  const [entries, setEntries] = useState<AnalysisOutputEntry[] | null>(null);
  const [sel, setSel] = useState<string | null>(null);

  useEffect(() => {
    setEntries(null); setSel(null);
    if (!outputDir) return;
    analysisApiOutputs.list(outputDir).then((r) => {
      setEntries(r.entries);
      const overview = r.entries.find((e) => e.kind === "md" && e.name.startsWith("00_"));
      setSel(overview?.path ?? r.entries.find((e) => e.kind === "md")?.path ?? null);
    }).catch(() => setEntries([]));
  }, [outputDir]);

  if (!outputDir) return <p className="text-xs text-slate-400">分析运行完成后自动填充（Analysis 阶段）。</p>;

  return (
    <div className="space-y-2">
      <div className="flex gap-1 text-[11px]">
        <button onClick={() => setMode("report")}
                className={`rounded border px-2 py-1 ${mode === "report"
                  ? "border-blue-300 bg-blue-50 text-blue-700" : "border-slate-200 hover:bg-slate-50"}`}>
          交互式科学发现报告
        </button>
        <button onClick={() => setMode("raw")}
                className={`rounded border px-2 py-1 ${mode === "raw"
                  ? "border-blue-300 bg-blue-50 text-blue-700" : "border-slate-200 hover:bg-slate-50"}`}>
          原始产物
        </button>
      </div>
      {mode === "report" ? <ScientificReport outputDir={outputDir} /> : (
        !entries ? <p className="text-xs text-slate-400">正在加载报告…</p> : (
          <div className="grid gap-3 md:grid-cols-[180px_1fr]">
            <ul className="space-y-0.5 text-xs">
              {entries.filter((e) => e.kind === "md").map((e) => (
                <li key={e.path}>
                  <button onClick={() => setSel(e.path)}
                          className={`w-full truncate rounded px-2 py-1 text-left ${sel === e.path ? "bg-blue-50 text-blue-700" : "hover:bg-slate-50"}`}>
                    {e.name}
                  </button>
                </li>
              ))}
            </ul>
            <div className="max-h-[520px] overflow-y-auto rounded-lg border border-slate-200 bg-white p-4">
              {sel ? <MarkdownViewer path={sel} /> : <p className="text-xs text-slate-400">请选择左侧报告</p>}
            </div>
          </div>
        )
      )}
    </div>
  );
}
