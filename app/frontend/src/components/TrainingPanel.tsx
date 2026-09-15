import { useEffect, useMemo, useState } from "react";
import { trainingApi, type DevicePolicy, type PreflightCheck } from "../api/training";
import { pipelineApi } from "../api/pipeline";
import type { RunManifest } from "../api/training";
import { RunLogViewer } from "./RunLogViewer";
import { StepRunner } from "./StepRunner";

const SPLITS = ["single", "all", "mixed"];

/** 候选生成：由用户自行决定用哪些模型做预测（默认沿用训练所选模型）。 */
function CandidateRunner({ outputDir, dataDir, cellLines, defaultModels, onOpenFile }:
  {
    outputDir: string;
    dataDir: string;
    cellLines: string[];
    defaultModels: string[];
    onOpenFile?: (path: string) => void;
  }) {
  const [predModels, setPredModels] = useState<string[]>(defaultModels);
  const [topK, setTopK] = useState(20);
  const [dryRun, setDryRun] = useState(false);
  const [busy, setBusy] = useState(false);
  const [run, setRun] = useState<RunManifest | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const toggle = (m: string) =>
    setPredModels((s) => (s.includes(m) ? s.filter((x) => x !== m) : [...s, m]));

  const start = async () => {
    if (!predModels.length) { setErr("请至少选择一个模型"); return; }
    if (!dryRun && !window.confirm(
      `将用 ${predModels.join(", ")} 做候选生成（写入 ${outputDir}/results/summary/）。确认执行？`)) return;
    setBusy(true); setErr(null);
    try {
      const r = await pipelineApi.run("generate_candidates", {
        dry_run: dryRun, output_dir: outputDir,
        ...(dataDir ? { data_dir: dataDir } : {}),
        options: { models: predModels, cell_lines: cellLines, candidate_top_k: topK },
      });
      if (r.run_id) setRun(r as RunManifest);
      else setErr(String(r.message ?? r.status));
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally { setBusy(false); }
  };

  return (
    <div className="mt-3 rounded-lg border border-dashed border-slate-300 p-2.5">
      <div className="flex flex-wrap items-center gap-2 text-[11px]">
        <span className="font-semibold text-slate-600">候选生成与优先级排序</span>
        <span className="text-slate-400">选择用于预测的模型（可与训练模型不同）</span>
        <span className="ml-auto">Top-K</span>
        <input type="number" min={1} value={topK} onChange={(e) => setTopK(Number(e.target.value))}
               className="w-16 rounded border border-slate-200 px-1 py-0.5" />
        <label className="flex items-center gap-1 text-slate-500">
          <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} /> dry-run 预览
        </label>
        <button onClick={() => void start()} disabled={busy || !predModels.length}
                className="rounded-md bg-slate-800 px-2 py-0.5 text-white hover:bg-slate-900 disabled:opacity-40">
          {busy ? "执行中…" : "生成候选"}
        </button>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1">
        {ALL_MODELS.map((m) => (
          <label key={m} className="flex items-center gap-1 rounded border border-slate-200 px-1.5 py-0.5 text-[11px] hover:bg-slate-50">
            <input type="checkbox" checked={predModels.includes(m)} onChange={() => toggle(m)} />{m}
          </label>
        ))}
        <button onClick={() => setPredModels(ALL_MODELS)} className="text-[10px] text-blue-600 hover:underline">全选</button>
        <button onClick={() => setPredModels([])} className="text-[10px] text-slate-500 hover:underline">清空</button>
        {onOpenFile && (
          <button onClick={() => onOpenFile(`${outputDir}/results/summary/赛道二_results.csv`)}
                  className="ml-auto text-[10px] text-blue-600 hover:underline">查看已有候选清单</button>
        )}
      </div>
      {err && <p className="mt-1 text-[11px] text-red-600">{err}</p>}
      {run && <div className="mt-2"><RunLogViewer run={run} onRun={setRun} title="候选生成输出（实时）" /></div>}
    </div>
  );
}
const ALL_MODELS = ["linear", "xgboost", "mlp", "cnn", "transformer"];
const DEFAULT_EPI = ["ctcf", "dnase", "h3k4me3", "rrbs"];

/**
 * Cell 05 · Training / Device
 * - Cells 与 Scope epi 的选项**来自用户数据集的探测结果**（不再硬编码）；
 * - Device 取代 Runtime（只显示 cpu / gpu / cpu/gpu），并按所选模型锁定/开放；
 * - 需要用户填写训练结果输出目标文件夹（results dir），Analysis 阶段直接复用。
 */
export function TrainingPanel({ projectId, outputDir, dataDir, modelDir, logsDir,
                              cellLines, channels, saved, onSaved, onOpenFile }:
  {
    projectId: string;
    outputDir: string;                 // 绝对输出目录
    dataDir: string;
    modelDir: string;
    logsDir: string;
    cellLines: string[];
    channels: string[];
    saved?: { models?: string[]; cell_lines?: string[]; split_types?: string[]; scope_epi?: string[]; device?: string } | null;
    onSaved: (patch: Record<string, unknown>) => Promise<void> | void;
    onOpenFile?: (path: string) => void;
  }) {
  const [models, setModels] = useState<string[]>(saved?.models ?? ["xgboost"]);
  const [cells, setCells] = useState<string[]>(saved?.cell_lines ?? []);
  const [splits, setSplits] = useState<string[]>(saved?.split_types ?? ["single"]);
  const [scope, setScope] = useState<string[]>(saved?.scope_epi ?? []);
  const [device, setDevice] = useState<string>(saved?.device ?? "cpu");
  const [epochs, setEpochs] = useState(100);
  const [dryRun, setDryRun] = useState(true);
  const [policy, setPolicy] = useState<DevicePolicy | null>(null);
  const [checks, setChecks] = useState<PreflightCheck[] | null>(null);
  const [run, setRun] = useState<RunManifest | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const dataCells = cellLines.length ? cellLines : [];
  const dataChannels = channels.length ? channels.map((c) => c.toLowerCase()) : DEFAULT_EPI;

  useEffect(() => {                                   // 首次进入用探测结果做默认勾选
    if (!cells.length && dataCells.length) setCells([dataCells[0]]);
    if (!scope.length && channels.length) setScope(dataChannels.slice(0, 2));
  }, [dataCells.length, dataChannels.length]);        // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {                                   // Device 策略随模型变化
    trainingApi.devicePolicy(models).then((p) => {
      setPolicy(p);
      setDevice((d) => (p.allowed.includes(d) ? d : p.allowed[0]));
    }).catch((e) => setErr(String(e)));
  }, [models.join(",")]);                             // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (arr: string[], set: (v: string[]) => void, v: string) =>
    set(arr.includes(v) ? arr.filter((x) => x !== v) : [...arr, v]);

  const chip = (label: string, items: string[], arr: string[], set: (v: string[]) => void) => (
    <div className="flex flex-wrap items-center gap-1">
      <span className="w-24 text-[11px] text-slate-500">{label}</span>
      {items.length === 0 && <span className="text-[11px] text-amber-600">（请先在 Cell 02 运行数据集探测）</span>}
      {items.map((v) => (
        <label key={v} className="flex items-center gap-1 rounded border border-slate-200 px-1.5 py-0.5 text-[11px] hover:bg-slate-50">
          <input type="checkbox" checked={arr.includes(v)} onChange={() => toggle(arr, set, v)} />{v}
        </label>
      ))}
    </div>
  );

  const resultsDir = useMemo(() => `${outputDir.replace(/\/$/, "")}/results`, [outputDir]);

  const buildOptions = () => ({
    models, cell_lines: cells, split_types: splits,
    training_scope_epis: scope.length ? scope : undefined,
    epochs, device,
  });

  const preflight = () => {
    trainingApi.preflight({
      kind: "dig", models, cell_lines: cells, split_types: splits,
      training_scope_epis: scope, epochs, runtime: "local_cpu",
      data_dir: dataDir, results_dir: resultsDir,
      model_dir: modelDir, logs_dir: logsDir, device, dry_run: dryRun,
    }).then((r) => setChecks(r.checks)).catch((e) => setErr(String(e)));
  };

  const submit = async () => {
    setErr(null);
    if (!dryRun && !window.confirm(
      `将真实训练并写入\n  ${resultsDir}\n  ${modelDir}\n  ${logsDir}\n（Device=${device}）。确认执行？`)) return;
    try {
      await onSaved({ models, cell_lines: cells, split_types: splits,
                      scope_epi: scope, device });
      const m = await pipelineApi.run("train_grid", {
        dry_run: dryRun, output_dir: outputDir,
        data_dir: dataDir,
        options: buildOptions(),
      });
      if (m.run_id) setRun(m as RunManifest);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  };

  return (
    <div className="space-y-3 text-sm">
      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-2 rounded-lg border border-slate-200 p-3">
          <p className="text-xs font-semibold text-slate-600">
            训练配置（细胞系 / 表观通道选项来自 Cell 02 的数据集探测结果）
          </p>
          {chip("模型", ALL_MODELS, models, setModels)}
          {chip("细胞系", dataCells, cells, setCells)}
          {chip("数据划分", SPLITS, splits, setSplits)}
          {chip("表观通道", dataChannels, scope, setScope)}
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="w-24 text-slate-500">Device</span>
            <select value={device} onChange={(e) => setDevice(e.target.value)}
                    disabled={!!policy?.locked}
                    className="rounded border border-slate-200 px-1.5 py-1">
              {(policy?.allowed ?? ["cpu"]).map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
            {policy?.locked && <span className="text-amber-700">已按模型锁定（线性/树模型仅 CPU）</span>}
            <label className="flex items-center gap-1">
              <input type="checkbox" checked={dryRun} onChange={(e) => setDryRun(e.target.checked)} />
              dry-run（只校验，不真跑）
            </label>
          </div>
          {policy?.note && <p className="text-[10px] text-slate-500">{policy.note}</p>}
          <div className="flex flex-wrap items-center gap-2 text-[11px]">
            <span className="w-24 text-slate-500">epochs</span>
            <input type="number" value={epochs} min={1} onChange={(e) => setEpochs(Number(e.target.value))}
                   className="w-16 rounded border border-slate-200 px-1.5 py-0.5" />
            <span className="text-slate-500">训练结果目录：</span>
            <span className="font-mono text-[10px]">{resultsDir}</span>
          </div>
        </div>

        <div className="space-y-2 rounded-lg border border-slate-200 p-3">
          <p className="text-xs font-semibold text-slate-600">Actions</p>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => void preflight()}
                    className="rounded-md border border-slate-300 px-3 py-1 hover:bg-slate-50">预检查</button>
            <button onClick={() => void submit()} disabled={!models.length || !cells.length}
                    className="rounded-md bg-blue-600 px-3 py-1 text-white hover:bg-blue-700 disabled:opacity-50">
              {dryRun ? "预览训练" : "开始训练"}
            </button>
          </div>
          {checks && (
            <ul className="max-h-40 space-y-0.5 overflow-auto text-[11px]">
              {checks.map((c, i) => (
                <li key={i} className="flex items-center gap-1.5">
                  <span className={c.ok ? "text-emerald-600" : "text-red-600"}>{c.ok ? "✓" : "✗"}</span>
                  <span>{c.check}</span><span className="text-slate-400">{c.message}</span>
                </li>
              ))}
            </ul>
          )}
          {err && <p className="text-[11px] text-red-600">{err}</p>}
        </div>
      </div>

      <RunLogViewer run={run} onRun={setRun} title="训练输出（实时）" />

      <CandidateRunner outputDir={outputDir} dataDir={dataDir} cellLines={cells}
                       defaultModels={models} onOpenFile={onOpenFile} />
    </div>
  );
}
