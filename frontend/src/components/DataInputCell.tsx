import { useState } from "react";
import { datasetApi, type DatasetInspection } from "../api/dataset";
import { DirPicker } from "./DirPicker";

/**
 * Cell 02 · Data Input：通过**目录弹窗**选择已测/待测数据集（绝对路径），
 * 并运行"数据集探测"程序 → 得到 cell line 与 channel（供 Mapping 与 Training 使用）。
 */
export function DataInputCell({ projectId, measured, target, inspection, onSaved }:
  {
    projectId: string;
    measured: string[];
    target: string[];
    inspection?: DatasetInspection | null;
    onSaved: (patch: Record<string, unknown>, inspection: DatasetInspection) => Promise<void> | void;
  }) {
  const [measuredPaths, setMeasuredPaths] = useState<string[]>(measured);
  const [targetPaths, setTargetPaths] = useState<string[]>(target);
  const [pickFor, setPickFor] = useState<"measured" | "target" | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [info, setInfo] = useState<DatasetInspection | null>(inspection ?? null);

  const addPath = (p: string) => {
    if (pickFor === "measured") setMeasuredPaths((s) => (s.includes(p) ? s : [...s, p]));
    else if (pickFor === "target") setTargetPaths((s) => (s.includes(p) ? s : [...s, p]));
    setPickFor(null);
  };

  const list = (paths: string[], which: "measured" | "target") => (
    <ul className="space-y-1">
      {paths.map((p) => (
        <li key={p} className="flex items-center gap-2 rounded border border-slate-200 px-2 py-1">
          <code className="flex-1 truncate text-[11px]" title={p}>{p}</code>
          <button onClick={() => (which === "measured"
            ? setMeasuredPaths((s) => s.filter((x) => x !== p))
            : setTargetPaths((s) => s.filter((x) => x !== p)))}
                  className="text-[10px] text-red-600 hover:underline">移除</button>
        </li>
      ))}
      {paths.length === 0 && <li className="text-[11px] text-slate-400">（尚未选择）</li>}
    </ul>
  );

  const inspect = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await datasetApi.inspect(measuredPaths);
      setInfo(r);
      await onSaved({
        data_dir: undefined,
        target_paths: targetPaths,
        cell_lines: r.cell_lines,
        scope_epi: r.channels.map((c) => c.toLowerCase()),
      }, r);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-3 text-sm">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-1">
          <p className="text-xs font-semibold text-slate-600">已测数据集（绝对路径）</p>
          {list(measuredPaths, "measured")}
          <button onClick={() => setPickFor("measured")}
                  className="rounded-md border border-slate-300 px-2 py-1 text-[11px] hover:bg-slate-50">
            选择目录…
          </button>
        </div>
        <div className="space-y-1">
          <p className="text-xs font-semibold text-slate-600">待测数据集（可选，用于候选设计）</p>
          {list(targetPaths, "target")}
          <button onClick={() => setPickFor("target")}
                  className="rounded-md border border-slate-300 px-2 py-1 text-[11px] hover:bg-slate-50">
            选择目录…
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <button onClick={() => void inspect()} disabled={busy || !measuredPaths.length}
                className="rounded-md bg-blue-600 px-3 py-1 text-white hover:bg-blue-700 disabled:opacity-40">
          {busy ? "探测中…" : "运行数据集探测"}
        </button>
        <span className="text-slate-400">探测程序只读用户数据；结果决定 Mapping 选项与 Training 的 Cells / Scope epi</span>
      </div>
      {err && <p className="text-[11px] text-red-600">{err}</p>}

      {info && (
        <div className="rounded-lg border border-slate-200 p-2 text-[11px]" data-testid="inspection-result">
          <p><span className="text-slate-500">细胞系：</span>{info.cell_lines.join(", ") || "—"}</p>
          <p><span className="text-slate-500">表观通道：</span>{info.channels.join(", ") || "—"}</p>
          <p><span className="text-slate-500">序列/标签列：</span>{info.sequence_column ?? "—"} / {info.label_column ?? "—"}
            <span className="text-slate-500">　长度：</span>{info.sequence_length || "—"}</p>
          <p className={info.requires_mapping ? "text-amber-700" : "text-emerald-700"}>
            待 Mapping 符号：{info.pending_mapping} 项{info.requires_mapping ? "（见 Cell 04）" : "（无需人工确认）"}
          </p>
        </div>
      )}

      <DirPicker open={pickFor !== null} title={pickFor === "target" ? "选择待测数据集目录" : "选择已测数据集目录"}
                 onClose={() => setPickFor(null)} onPick={addPath} />
    </div>
  );
}
