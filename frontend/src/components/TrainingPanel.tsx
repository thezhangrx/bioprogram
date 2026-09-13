import { useEffect, useMemo, useState } from "react";
import { trainingApi, type DevicePolicy, type PreflightCheck } from "../api/training";
import { pipelineApi } from "../api/pipeline";
import type { RunManifest } from "../api/training";
import { RunLogViewer } from "./RunLogViewer";
import { StepRunner } from "./StepRunner";

const SPLITS = ["single", "all", "mixed"];
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
            Training Configuration（Cells / Scope 来自 Cell 02 的探测结果）
          </p>
          {chip("Models", ALL_MODELS, models, setModels)}
          {chip("Cells", dataCells, cells, setCells)}
          {chip("Splits", SPLITS, splits, setSplits)}
          {chip("Scope epi", dataChannels, scope, setScope)}
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
                    className="rounded-md border border-slate-300 px-3 py-1 hover:bg-slate-50">Preflight Check</button>
            <button onClick={() => void submit()} disabled={!models.length || !cells.length}
                    className="rounded-md bg-blue-600 px-3 py-1 text-white hover:bg-blue-700 disabled:opacity-50">
              {dryRun ? "Preview Training" : "Run Training"}
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

      <RunLogViewer run={run} onRun={setRun} title="Training output（实时 print）" />

      <StepRunner stepIds={["generate_candidates"]} outputDir={outputDir}
                  contextOverrides={{ data_dir: dataDir }}
                  runOptions={{ models, cell_lines: cells, candidate_top_k: 20, epochs: 15, seed: 42, device }}
                  onOpenFile={onOpenFile} title="候选生成（可选步骤）" />
    </div>
  );
}
