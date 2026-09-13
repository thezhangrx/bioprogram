import { useEffect, useState } from "react";
import { trainingApi, type RunManifest } from "../api/training";

export function RunsHistory() {
  const [runs, setRuns] = useState<RunManifest[]>([]);
  const [log, setLog] = useState<{ id: string; lines: string[] } | null>(null);
  useEffect(() => {
    void trainingApi.runs().then(setRuns).catch(() => undefined);
  }, []);
  const openLog = async (id: string) => {
    const r = await trainingApi.log(id);
    setLog({ id, lines: r.lines });
  };
  return (
    <div className="space-y-1 p-3 text-xs">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">Runs / History</p>
      {runs.length === 0 && <p className="text-slate-400">暂无运行记录</p>}
      {runs.map((r) => (
        <div key={r.run_id} className="rounded-md border border-slate-100 p-1.5">
          <div className="flex items-center justify-between gap-1">
            <button onClick={() => void openLog(r.run_id)} className="truncate font-mono text-[10px] hover:underline">{r.run_id}</button>
            <span className={`text-[10px] ${r.status === "completed" ? "text-emerald-600" : r.status === "running" ? "text-blue-600" : r.status === "failed" ? "text-red-600" : "text-slate-400"}`}>{r.status}</span>
          </div>
          {log?.id === r.run_id && (
            <pre className="mt-1 max-h-24 overflow-auto rounded bg-slate-900 p-1 text-[9px] leading-snug text-slate-200">
              {log.lines.slice(-30).join("\n") || "(empty log)"}
            </pre>
          )}
        </div>
      ))}
    </div>
  );
}
