import { useMemo, useState } from "react";
import { datasetApi, type DatasetInspection } from "../api/dataset";
import { pipelineApi } from "../api/pipeline";
import type { RunManifest } from "../api/training";
import { RunLogViewer } from "./RunLogViewer";

/**
 * Cell 04 · User Decision / Mapping（在数据探测程序运行完之后才显示内容）。
 * 逐通道列出数据集中实际出现的符号（例如 A 与 N），由用户决定如何映射为 0/1；
 * 保存后立即在同一 cell 内触发**特征工程**（可选步骤，默认需用户勾选）。
 */
export function MappingCell({ projectId, inspection, savedConfig, outputDir, onSaved, onOpenFile }:
  {
    projectId: string;
    outputDir: string;
    inspection: DatasetInspection | null;
    savedConfig?: { feature_config?: string; mapping_decisions?: Record<string, number> } | null;
    onSaved: (patch: Record<string, unknown>) => Promise<void> | void;
    onOpenFile?: (path: string) => void;
  }) {
  const [decisions, setDecisions] = useState<Record<string, number>>(
    savedConfig?.mapping_decisions ?? {});
  const [configPath, setConfigPath] = useState<string | null>(savedConfig?.feature_config ?? null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [feRun, setFeRun] = useState<RunManifest | null>(null);
  const [feMsg, setFeMsg] = useState<string | null>(null);

  const items = useMemo(() => inspection?.mapping_items ?? [], [inspection]);

  if (!inspection) {
    return (
      <p className="text-xs text-amber-600">
        Waiting for dependency: 请先在 Cell 02「Data Input」运行**数据集探测**，
        探测完成后这里会列出需要 Mapping 的符号（例如 A、N）。
      </p>
    );
  }

  const key = (scope: string, channel: string | null, symbol: string) =>
    scope === "channel" ? `${channel}:${symbol}` : `seq:${channel}:${symbol}`;

  /** 运行特征工程（**必做步骤**：Mapping 保存后必须执行，不是可选项）。 */
  const runFeatureEngineering = async (configPath?: string | null, dryRun = false) => {
    setFeMsg(null); setErr(null);
    try {
      const r = await pipelineApi.run("feature_engineering", {
        dry_run: dryRun, output_dir: outputDir,
        ...(configPath ? { feature_config: configPath } : {}),
      });
      if (r.run_id) setFeRun(r as RunManifest);
      else setFeMsg(r.message ?? r.status);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };

  const save = async () => {
    setBusy(true); setErr(null);
    try {
      const r = await datasetApi.mappingConfig({
        inspection, decisions, project_id: projectId,
      });
      setConfigPath(r.config_path);
      await onSaved({ feature_config: r.config_path, mapping_decisions: decisions });
      await runFeatureEngineering(r.config_path);       // 保存后立即执行（必做）
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const ambiguous = items.filter((i) => i.ambiguous);

  return (
    <div className="space-y-3 text-sm">
      <div className="rounded-lg border border-slate-200 p-2 text-[11px]">
        <p><span className="text-slate-500">来源数据集：</span>{inspection.inputs.join(", ")}</p>
        <p><span className="text-slate-500">细胞系：</span>{inspection.cell_lines.join(", ") || "—"}
          <span className="text-slate-500">　通道：</span>{inspection.channels.join(", ") || "—"}</p>
        <p className={ambiguous.length ? "text-amber-700" : "text-emerald-700"}>
          需要人工确认的符号：{ambiguous.length} 项
          {ambiguous.length > 0 && `（${[...new Set(ambiguous.map((a) => a.symbol))].join(", ")}）`}
        </p>
      </div>

      <table className="w-full text-[11px]">
        <thead className="bg-slate-50 text-slate-500">
          <tr>
            <th className="border px-2 py-1 text-left">范围</th>
            <th className="border px-2 py-1 text-left">通道/列</th>
            <th className="border px-2 py-1 text-left">符号</th>
            <th className="border px-2 py-1 text-left">出现样本数</th>
            <th className="border px-2 py-1 text-left">映射为</th>
          </tr>
        </thead>
        <tbody>
          {items.map((it) => {
            const k = key(it.scope, it.channel, it.symbol);
            const cur = decisions[k] ?? it.default_value;
            return (
              <tr key={k} className={it.ambiguous ? "bg-amber-50/60" : ""}>
                <td className="border px-2 py-1">{it.scope === "channel" ? "表观通道" : "序列"}</td>
                <td className="border px-2 py-1">{it.channel ?? "—"}</td>
                <td className="border px-2 py-1 font-mono">{it.symbol}{it.ambiguous ? " ⚠" : ""}</td>
                <td className="border px-2 py-1">{it.n_samples_with_symbol}</td>
                <td className="border px-2 py-1">
                  <select value={cur}
                          onChange={(e) => setDecisions((d) => ({ ...d, [k]: Number(e.target.value) }))}
                          className="rounded border border-slate-200 px-1 py-0.5">
                    {it.options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                  </select>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <button onClick={() => void save()} disabled={busy}
                className="rounded-md bg-blue-600 px-3 py-1 text-white hover:bg-blue-700 disabled:opacity-40">
          {busy ? "保存中…" : "保存 Mapping 配置"}
        </button>
        {configPath && (
          <span className="font-mono text-[10px] text-slate-500">
            已写入 {configPath}{onOpenFile ? "" : ""}
          </span>
        )}
        {configPath && onOpenFile && (
          <button onClick={() => onOpenFile(configPath)}
                  className="rounded border border-slate-300 px-2 py-0.5 text-[10px] hover:bg-slate-50">
            查看配置
          </button>
        )}
      </div>
      {err && <p className="text-[11px] text-red-600">{err}</p>}

      <div className="rounded-lg border border-blue-200 bg-blue-50/40 p-2.5">
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span className="font-semibold text-blue-800">特征工程（必做步骤）</span>
          <span className="text-slate-500">
            Mapping 保存后自动执行；也可在此重新执行。依赖：探测结果 + 用户映射配置。
          </span>
          <span className="flex-1" />
          <button onClick={() => void runFeatureEngineering(configPath, true)}
                  className="rounded border border-slate-300 bg-white px-2 py-0.5 text-[10px] hover:bg-slate-50">
            dry-run 预览
          </button>
          <button onClick={() => void runFeatureEngineering(configPath)}
                  disabled={!configPath}
                  className="rounded-md bg-blue-600 px-2 py-0.5 text-[10px] text-white hover:bg-blue-700 disabled:opacity-40">
            重新执行特征工程
          </button>
        </div>
        {feMsg && <p className="mt-1 text-[11px] text-slate-600">{feMsg}</p>}
        {feRun && (
          <div className="mt-2">
            <RunLogViewer run={feRun} onRun={setFeRun} title="特征工程输出（实时）" />
          </div>
        )}
      </div>
    </div>
  );
}
