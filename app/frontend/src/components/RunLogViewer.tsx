import { useEffect, useRef, useState } from "react";
import { trainingApi, type RunManifest } from "../api/training";

/**
 * 实时运行日志：轮询 /api/runs/<id>/log，把训练/流程脚本 print 到 stdout 的文字
 * 原样展示（子进程 stdout+stderr 合并写 run.log），并显示状态、进度与取消/续跑。
 */
export function RunLogViewer({ run, onRun, pollMs = 1500, title = "实时输出" }:
  { run: RunManifest | null; onRun?: (r: RunManifest) => void; pollMs?: number; title?: string }) {
  const [lines, setLines] = useState<string[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const boxRef = useRef<HTMLPreElement | null>(null);
  const active = run?.status === "running" || run?.status === "submitted_external";

  useEffect(() => {
    if (!run?.run_id) { setLines([]); return; }
    let cancelled = false;
    let timer: number | null = null;

    const tick = async () => {
      try {
        const r = await trainingApi.log(run.run_id);
        if (cancelled) return;
        setLines(r.lines);
        if (active) {
          const st = await trainingApi.status(run.run_id);
          if (cancelled) return;
          onRun?.(st);
          if (st.status === "running") timer = window.setTimeout(() => void tick(), pollMs);
        }
      } catch (e) {
        if (!cancelled) setErr(String(e));
      }
    };
    void tick();
    return () => { cancelled = true; if (timer) window.clearTimeout(timer); };
  }, [run?.run_id, run?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const el = boxRef.current;
    if (el) el.scrollTop = el.scrollHeight;      // 跟随最新输出
  }, [lines]);

  if (!run) return <p className="text-[11px] text-slate-400">尚无运行记录。</p>;
  const p = run.progress?.ratio ?? null;
  return (
    <div className="rounded-lg border border-slate-200 p-3" data-testid="run-log-viewer">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="font-semibold text-slate-600">{title}</span>
        <span className="font-mono">{run.run_id}</span>
        <span className={
          run.status === "running" ? "text-blue-600"
            : run.status === "completed" ? "text-emerald-600"
              : run.status === "failed" ? "text-red-600" : "text-slate-500"}>{run.status}</span>
        {run.progress && run.progress.total ? (
          <span className="text-slate-400">{run.progress.done}/{run.progress.total}</span>
        ) : null}
        {active && (
          <button onClick={() => void trainingApi.cancel(run.run_id).then((r) => onRun?.(r))}
                  className="rounded border border-red-200 px-2 py-0.5 text-red-600 hover:bg-red-50">
            取消
          </button>
        )}
        {(run.status === "failed" || run.status === "cancelled") && (
          <button onClick={() => void trainingApi.resume(run.run_id).then((r) => onRun?.(r))}
                  className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-50">
            继续
          </button>
        )}
      </div>
      {run.command && <p className="mt-1 break-all text-[10px] text-slate-400">$ {run.command}</p>}
      {p != null && (
        <div className="mt-2 h-1.5 w-full overflow-hidden rounded bg-slate-100">
          <div className="h-full bg-blue-500" style={{ width: `${Math.round(p * 100)}%` }} />
        </div>
      )}
      <pre ref={boxRef} data-testid="run-log-text"
           className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap rounded bg-slate-900 p-2 text-[10px] leading-snug text-slate-100">
        {lines.join("\n") || "（暂无输出）"}
      </pre>
      {err && <p className="mt-1 text-[11px] text-red-600">{err}</p>}
    </div>
  );
}
