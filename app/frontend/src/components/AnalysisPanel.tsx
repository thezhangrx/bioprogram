import { useEffect, useState } from "react";
import { analysisApi, analysisApiOutputs, type AnalysisTask } from "../api/analysis";
import { ArtifactViewer } from "./artifacts/ArtifactViewer";

const GROUPS: [string, string][] = [
  ["core", "核心任务"],
  ["advanced", "进阶任务"],
];

export function AnalysisPanel({ projectId, trainingResultsDir, outputRoot, onCompleted }:
  { projectId: string; trainingResultsDir: string; outputRoot: string;
    onCompleted?: (outDir: string) => void }) {
  const [tasks, setTasks] = useState<AnalysisTask[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set(["qc", "prediction"]));
  // 直接使用 Cell 01「Name」中选择的输出目录（绝对路径）；前端无 batch 概念
  const resultsDir = trainingResultsDir;
  const [run, setRun] = useState<{ output: string; running: boolean; err?: string; report?: string } | null>(null);

  const load = () => analysisApi.tasks(resultsDir || undefined).then(setTasks).catch(() => setTasks([]));
  useEffect(() => { void load(); }, []); // eslint-disable-line

  const toggle = (id: string) => {
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  };

  const launch = async () => {
    setRun({ output: "", running: true });
    try {
      const m = await analysisApi.run(resultsDir, [...selected], projectId);
      const out = m.output_dir;
      const poll = async () => {
        const st = await analysisApi.status(out);
        if (st.status === "completed") {
          // 报告位于 <out>/reports/（新布局）或 <out>/summary/（旧布局），以产物清单为准
          let report = `${out}/reports/00_overview.md`;
          try {
            const { entries } = await analysisApiOutputs.list(out);
            const hit = entries.find((e) => e.name === "00_overview.md")
              ?? entries.find((e) => e.name.endsWith("_overview.md"));
            if (hit) report = hit.path;
          } catch { /* 清单不可用时回退到默认路径 */ }
          setRun({ output: out, running: false, report });
          onCompleted?.(out);
        } else if (st.status === "failed") {
          setRun({ output: out, running: false, err: "分析失败" });
        } else {
          setTimeout(() => void poll(), 1500);
        }
      };
      void poll();
    } catch (e) {
      setRun({ output: "", running: false, err: e instanceof Error ? e.message : String(e) });
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="text-slate-500">Training results（来自 Cell 01 的输出目录）:</span>
        <code className="rounded bg-slate-100 px-2 py-1 text-[11px]" data-testid="analysis-results-dir">{resultsDir || "—"}</code>
        <span className="text-slate-400">输出根：{outputRoot || "—"}</span>
        <button onClick={() => void load()} className="rounded-md border border-slate-200 px-2 py-1 hover:bg-slate-50">刷新</button>
        <span className="ml-auto text-slate-400">任务目录来自 Analyse Registry</span>
      </div>

      {GROUPS.map(([key, label]) => (
        <fieldset key={key}>
          <legend className="text-xs font-semibold text-slate-600">{label}</legend>
          <div className="grid grid-cols-2 gap-1 pl-1 text-xs">
            {tasks.filter((t) => (t.category || "core") === key).map((t) => {
              const dis = t.available === false;
              return (
                <label key={t.task_id} className={`flex items-center gap-2 rounded-md px-2 py-1 ${dis ? "opacity-60" : "hover:bg-slate-50"}`} title={dis ? t.reason : t.display}>
                  <input type="checkbox" disabled={dis} checked={selected.has(t.task_id)}
                         onChange={() => toggle(t.task_id)} />
                  <span>{t.display}</span>
                  {dis && <span className="text-[10px] text-rose-500">不可用</span>}
                </label>
              );
            })}
            {tasks.filter((t) => (t.category || "core") === key).length === 0 && <p className="text-slate-400">（无）</p>}
          </div>
        </fieldset>
      ))}

      <div className="flex items-center gap-2">
        <button onClick={() => void launch()} disabled={run?.running || !selected.size}
                className="rounded-md bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50">
          {run?.running ? "运行中…" : "运行分析"}
        </button>
        <span className="text-xs text-slate-400">已选 {selected.size} 项 · 每个任务的状态见 analysis_status.json</span>
      </div>
      {run?.err && <p className="text-xs text-red-600">{run.err}</p>}
      {run?.report && <ArtifactViewer path={run.report} kind="md" />}
    </div>
  );
}
