import { useCallback, useEffect, useRef, useState } from "react";
import { pipelineApi, type PipelineStep } from "../api/pipeline";
import type { RunManifest } from "../api/training";
import { artifactLabel, canRun, confirmText, statusTone } from "../lib/pipeline";
import { RunLogViewer } from "./RunLogViewer";

/**
 * 把一个阶段的流程步骤**嵌入**到该阶段 cell 中（不再有独立 Pipeline 模块）。
 * 每个步骤都有勾选框，用户自行决定是否执行（默认不勾选 = 可选步骤）。
 */
export function StepRunner({ stepIds, outputDir, contextOverrides, runOptions, onOpenFile,
                            title = "本阶段可选步骤", required = [], autoRunRequired = false }:
  {
    stepIds: string[];
    outputDir: string;
    /** 必做步骤：自动勾选且不可取消（例如 Mapping 之后的特征工程） */
    required?: string[];
    /** 是否在加载后立即执行必做步骤（默认否，由调用方显式触发） */
    autoRunRequired?: boolean;
    contextOverrides?: Record<string, unknown>;
    runOptions?: Record<string, unknown>;
    onOpenFile?: (path: string) => void;
    title?: string;
  }) {
  const [steps, setSteps] = useState<PipelineStep[]>([]);
  const [checked, setChecked] = useState<Set<string>>(new Set(required));
  const [busy, setBusy] = useState(false);
  const [dryRun, setDryRun] = useState(false);
  const [run, setRun] = useState<RunManifest | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    pipelineApi.steps(outputDir)
      .then((d) => setSteps(d.steps.filter((s) => stepIds.includes(s.step_id))))
      .catch((e) => setErr(String(e)));
  }, [outputDir, stepIds.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { load(); }, [load]);

  const toggle = (id: string) => {
    if (required.includes(id)) return;         // 必做步骤不可取消
    setChecked((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  };

  const runOne = async (step: PipelineStep) => {
    if (!canRun(step)) return;
    if (!dryRun && !window.confirm(confirmText(step))) return;
    try {
      const r = await pipelineApi.run(step.step_id, {
        dry_run: dryRun,
        output_dir: outputDir,
        ...(contextOverrides ?? {}),
        options: { ...(runOptions ?? {}) },
      });
      if (r.run_id) { setRun(r as RunManifest); return true; }
      setMsg(`${step.step_id}: ${r.message ?? r.status}`);
      return false;
    } catch (e) {
      setErr(String(e)); return false;
    }
  };

  // 必做步骤：由调用方通过 autoRunRequired 触发一次
  const autoRan = useRef(false);
  useEffect(() => {
    if (!autoRunRequired || autoRan.current || !steps.length) return;
    const pendingRequired = steps.filter((s) => required.includes(s.step_id) && canRun(s));
    if (!pendingRequired.length) return;
    autoRan.current = true;
    void (async () => {
      setBusy(true);
      for (const s of pendingRequired) { const asyncRun = await runOne(s); if (asyncRun) break; }
      setBusy(false); load();
    })();
  }, [autoRunRequired, steps]);   // eslint-disable-line react-hooks/exhaustive-deps

  const runSelected = async () => {
    const todo = steps.filter((s) => checked.has(s.step_id));
    if (!todo.length) { setMsg("请先勾选要执行的步骤"); return; }
    setBusy(true); setErr(null); setMsg(null);
    for (const s of todo) { const asyncRun = await runOne(s); if (asyncRun) break; }
    setBusy(false); load();
  };

  if (err && !steps.length) return <p className="text-[11px] text-red-600">{err}</p>;
  if (!steps.length) return <p className="text-[11px] text-slate-400">加载可选步骤…</p>;

  return (
    <div className="mt-3 rounded-lg border border-dashed border-slate-300 p-2.5">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="font-semibold text-slate-600">{title}</span>
        <span className="text-slate-400">（勾选后才会执行）</span>
        <label className="ml-auto flex items-center gap-1 text-slate-500">
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
          dry-run 预览
        </label>
        <button onClick={() => void runSelected()} disabled={busy || !checked.size}
                className="rounded-md bg-slate-800 px-2 py-0.5 text-white hover:bg-slate-900 disabled:opacity-40">
          {busy ? "执行中…" : `执行选中 (${checked.size})`}
        </button>
      </div>
      <ul className="mt-2 space-y-1">
        {steps.map((s) => (
          <li key={s.step_id} className="flex flex-wrap items-center gap-2 rounded border border-slate-100 px-2 py-1">
            <input type="checkbox" checked={checked.has(s.step_id)} onChange={() => toggle(s.step_id)}
                   disabled={required.includes(s.step_id)}
                   aria-label={`select-${s.step_id}`} />
            <span className={
              statusTone(s.status) === "ok" ? "size-2 rounded-full bg-emerald-500"
                : statusTone(s.status) === "warn" ? "size-2 rounded-full bg-amber-400"
                  : "size-2 rounded-full bg-slate-200"} />
            <span className="text-[11px] font-medium">{s.title}</span>
            <span className="text-[10px] text-slate-400">{s.status}</span>
            {required.includes(s.step_id) && <span className="rounded bg-blue-50 px-1 text-[10px] text-blue-700">必做</span>}
            {s.heavy && <span className="rounded bg-amber-50 px-1 text-[10px] text-amber-700">重任务·写 models/results/logs</span>}
            {!s.ready && <span className="text-[10px] text-slate-400">（依赖未完成）</span>}
            <span className="flex-1" />
            <button onClick={() => void runOne(s)} disabled={!canRun(s) || busy}
                    className="rounded border border-slate-300 px-1.5 py-0.5 text-[10px] hover:bg-slate-50 disabled:opacity-40">
              单独执行
            </button>
          </li>
        ))}
      </ul>
      <div className="mt-1.5 flex flex-wrap gap-1.5">
        {steps.flatMap((s) => s.artifacts.map((a) => (
          <button key={`${s.step_id}-${a.rel}`} onClick={() => a.exists && onOpenFile?.(a.path)}
                  title={a.path}
                  className={`rounded border px-1.5 py-0.5 text-[10px] ${a.exists
                    ? "border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                    : "border-slate-200 text-slate-400"}`}>
            {artifactLabel(a)}
          </button>
        )))}
      </div>
      {msg && <p className="mt-1 text-[11px] text-slate-600">{msg}</p>}
      {err && <p className="mt-1 text-[11px] text-red-600">{err}</p>}
      {run && <div className="mt-2"><RunLogViewer run={run} onRun={(r) => { setRun(r); if (r.status !== "running") load(); }} title="步骤输出" /></div>}
    </div>
  );
}
