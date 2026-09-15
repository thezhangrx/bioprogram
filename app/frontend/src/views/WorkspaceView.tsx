import { useEffect, useState } from "react";
import { projectApi } from "../api/project";
import { qcApi } from "../api/qc";
import { pipelineApi } from "../api/pipeline";
import { fsApi } from "../api/fs";
import { STAGE_ORDER, type ProjectManifest, type StageKey } from "../types";
import { NotebookCell } from "../components/NotebookCell";
import { ArtifactViewer } from "../components/artifacts/ArtifactViewer";
import { AnalysisPanel } from "../components/AnalysisPanel";
import { TrainingPanel } from "../components/TrainingPanel";
import { ReportsPanel } from "../components/ReportsPanel";
import { RunsHistory } from "../components/RunsHistory";
import { FileBrowser } from "../components/FileBrowser";
import { DataInputCell } from "../components/DataInputCell";
import { MappingCell } from "../components/MappingCell";
import { NameCell } from "../components/NameCell";
import { StepRunner } from "../components/StepRunner";
import type { DatasetInspection } from "../api/dataset";

const TITLES = {
  qc: "质量控制",
  mapping: "用户决策 / 映射",
  training: "训练 / 设备",
  analysis: "分析",
  reports: "报告",
} as const;

type Cfg = {
  output_dir?: string; data_dir?: string; feature_config?: string;
  mapping_decisions?: Record<string, number>; target_paths?: string[];
  inspection_summary?: Record<string, unknown>; device?: string;
  models?: string[]; cell_lines?: string[]; split_types?: string[]; scope_epi?: string[];
};

/** 后端返回的绝对路径上下文（Web 端不做任何路径拼接）。 */
interface PathContext {
  repo_root: string;
  output_dir: string; results_dir: string; model_dir: string; logs_dir: string;
  data_dir: string; raw_data_dir: string; feature_config: string;
}

export function WorkspaceView(props: { projectId: string; onExit: () => void }) {
  const [m, setM] = useState<ProjectManifest | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [runQc, setRunQc] = useState(false);
  const [qcSession, setQcSession] = useState<string | null>(null);
  const [filePath, setFilePath] = useState<string>("results");
  const [paths, setPaths] = useState<PathContext | null>(null);

  const refresh = () =>
    projectApi.open(props.projectId).then(setM)
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));

  useEffect(() => { void refresh(); }, [props.projectId]); // eslint-disable-line

  const cfg: Cfg = (m?.config as Cfg) ?? {};
  const inspection = ((m?.stage_detail?.mapping as { inspection?: DatasetInspection })?.inspection)
    ?? ((m?.stage_detail?.data as { inspection?: DatasetInspection })?.inspection) ?? null;

  // 首次进入：若未选择输出目录，则给一个工作区内的默认（可随项目一起删除）
  useEffect(() => {
    if (!m || cfg.output_dir) return;
    void fsApi.suggestOutput(props.projectId)
      .then((p) => projectApi.updateConfig(props.projectId, { output_dir: p }))
      .then(setM);
  }, [m?.project_id, cfg.output_dir]); // eslint-disable-line react-hooks/exhaustive-deps

  // 步骤上下文：所有绝对路径都来自后端
  useEffect(() => {
    if (!cfg.output_dir) return;
    void pipelineApi.steps(cfg.output_dir)
      .then((d) => setPaths(d.context as unknown as PathContext))
      .catch(() => undefined);
  }, [cfg.output_dir, m?.updated_at]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveConfig = async (patch: Cfg & { name?: string }) => {
    const next = await projectApi.updateConfig(props.projectId, patch);
    setM(next);
  };

  const onDataSaved = async (patch: Record<string, unknown>, insp: DatasetInspection) => {
    await projectApi.updateStage(props.projectId, "data", "completed", { inspection: insp });
    await saveConfig(patch as Cfg);
    await projectApi.updateStage(props.projectId, "mapping", "running", { inspection: insp });
  };

  if (err) return <p className="p-8 text-sm text-red-600">Open project failed — {err}</p>;
  if (!m) return <p className="p-8 text-sm text-slate-400">Loading project…</p>;

  const outputDir = paths?.output_dir ?? cfg.output_dir ?? "";
  const resultsDir = paths?.results_dir ?? (outputDir ? `${outputDir.replace(/\/$/, "")}/results` : "");
  const dataDir = paths?.data_dir ?? "";
  const modelDir = paths?.model_dir ?? "";
  const logsDir = paths?.logs_dir ?? "";
  const stageIndex = (k: StageKey) => STAGE_ORDER.indexOf(k) + 2;

  return (
    <div className="flex h-full">
      <aside className="w-60 shrink-0 border-r border-slate-200 bg-white">
        <div className="border-b border-slate-100 p-4">
          <p className="truncate text-sm font-semibold">{m.name}</p>
          <p className="font-mono text-[11px] text-slate-400">{m.project_id}</p>
          <button onClick={props.onExit} className="mt-2 text-[11px] text-blue-600 hover:underline">← All Projects</button>
        </div>
        <nav className="p-2 text-sm">
          <p className="px-2 py-1 text-[11px] text-slate-400">单元 01 · 名称</p>
          {STAGE_ORDER.map((k) => k === "data" ? (
            <p key={k} className="px-2 py-1.5 text-[11px] text-slate-400">单元 02 · 数据输入</p>
          ) : (
            <div key={k} className="flex w-full items-center justify-between rounded-md px-2 py-1.5 hover:bg-slate-50">
              <span className="text-slate-600">
                <span className="mr-1 font-mono text-[10px] text-slate-300">{stageIndex(k)}</span>{TITLES[k as keyof typeof TITLES]}
              </span>
            </div>
          ))}
          <p className="px-2 py-1 text-[11px] text-slate-400">单元 08 · 项目文件</p>
        </nav>
        <div className="border-t border-slate-100"><RunsHistory /></div>
      </aside>

      <main className="flex-1 space-y-4 overflow-y-auto p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">工作区</h2>
          <span className="text-xs text-slate-400">全部路径为绝对路径（由后端派生）</span>
        </div>

        {/* 单元 01 · 名称（项目名 + 输出目录弹窗） */}
        <NotebookCell index={1} title="名称（项目名 / 输出目录）" status={cfg.output_dir ? "completed" : "pending"}
          hint="项目名可随时修改；输出目录通过弹窗选择">
          <NameCell name={m.name} outputDir={outputDir} projectId={m.project_id}
                    repoRoot={(paths as unknown as { repo_root?: string })?.repo_root}
                    onRename={(name) => saveConfig({ name } as Cfg & { name: string })}
                    onPickOutput={(p) => saveConfig({ output_dir: p })} />
        </NotebookCell>

        {/* 单元 02 · 数据输入 */}
        <NotebookCell index={2} title="数据输入"
          status={inspection ? "completed" : "pending"}
          hint={(cfg.target_paths?.length ? `待测 ${cfg.target_paths.length} 个` : "选择已测/待测数据集")}>
          <DataInputCell projectId={m.project_id}
                         measured={(m.dataset.input_paths ?? [])}
                         target={cfg.target_paths ?? []}
                         inspection={inspection}
                         onSaved={onDataSaved} />
        </NotebookCell>

        {/* Cell 03 · QC */}
        <NotebookCell index={3} title={TITLES.qc} status={m.stages.qc}
          hint={qcSession ? `会话 ${qcSession}` : "对已导入的数据集运行 QC"}
          actions={
            <button disabled={runQc || !m.dataset.input_paths.length} onClick={async () => {
              setRunQc(true);
              try { setQcSession((await qcApi.start(m.dataset.input_paths, "workflow-qc")).session_id); }
              catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
              finally { setRunQc(false); }
            }} className="rounded-md bg-blue-600 px-2.5 py-1 text-white hover:bg-blue-700 disabled:opacity-40">
              {runQc ? "Running…" : "Run QC"}
            </button>
          }>
          {qcSession ? <ArtifactViewer path={`qc_sessions/${qcSession}/quality_report.md`} kind="md" />
            : <p className="text-xs text-slate-400">QC 尚未运行。</p>}
        </NotebookCell>

        {/* Cell 04 · User Decision / Mapping */}
        <NotebookCell index={4} title={TITLES.mapping} status={m.stages.mapping}
          hint={inspection?.requires_mapping
            ? `待确认 ${inspection.pending_mapping} 项（${[...new Set(inspection.mapping_items.filter((i) => i.ambiguous).map((i) => i.symbol))].join(", ")}）`
            : "探测完成后在此确认映射，并触发特征工程"}>
          <MappingCell projectId={m.project_id} inspection={inspection} outputDir={outputDir}
                       savedConfig={{ feature_config: cfg.feature_config,
                                      mapping_decisions: cfg.mapping_decisions }}
                       onSaved={async (patch) => {
                         await saveConfig(patch as Cfg);
                         await projectApi.updateStage(m.project_id, "mapping", "completed", patch);
                       }}
                       onOpenFile={(p) => setFilePath(p)} />
        </NotebookCell>

        {/* Cell 05 · Training / Device */}
        <NotebookCell index={5} title={TITLES.training} status={m.stages.training}
          hint={resultsDir || "（先在 Cell 01 选择输出目录）"}>
          <TrainingPanel projectId={m.project_id} outputDir={outputDir}
                         dataDir={dataDir} modelDir={modelDir} logsDir={logsDir}
                         cellLines={inspection?.cell_lines ?? []}
                         channels={inspection?.channels ?? []}
                         saved={{ models: cfg.models, cell_lines: cfg.cell_lines,
                                  split_types: cfg.split_types, scope_epi: cfg.scope_epi,
                                  device: cfg.device }}
                         onSaved={(patch) => saveConfig(patch as Cfg)}
                         onOpenFile={(p) => setFilePath(p)} />
        </NotebookCell>

        {/* Cell 06 · Analysis */}
        <NotebookCell index={6} title={TITLES.analysis} status={m.stages.analysis}
          hint={resultsDir || "—"}>
          <AnalysisPanel projectId={m.project_id} trainingResultsDir={resultsDir} outputRoot={outputDir}
                         onCompleted={(outDir) => {
                           void projectApi.updateStage(m.project_id, "analysis", "completed",
                             { output_dir: outDir }).then(refresh);
                         }} />
          <StepRunner stepIds={["collect_results", "anomaly_treatment", "importance_extraction",
                                "legacy_visualization", "analysis_engine"]}
                      outputDir={outputDir}
                      runOptions={{ split_types: cfg.split_types ?? ["single"] }}
                      onOpenFile={(p) => setFilePath(p)}
                      title="本阶段可选步骤（指标汇总 / 异常检测 / 特征库 / 全景图 / 分析引擎）" />
        </NotebookCell>

        {/* Cell 07 · Reports */}
        <NotebookCell index={7} title={TITLES.reports} status={m.stages.reports}>
          <ReportsPanel outputDir={analysisOutputOf(m)} />
          <StepRunner stepIds={["deliverables_check"]} outputDir={outputDir}
                      onOpenFile={(p) => setFilePath(p)} title="交付物核对（可选）" />
        </NotebookCell>

        {/* 单元 08 · 项目文件 */}
        <NotebookCell index={8} title="项目文件" status="completed" hint={filePath}>
          <FileBrowser path={filePath} onPathChange={setFilePath} />
        </NotebookCell>
      </main>
    </div>
  );
}

function analysisOutputOf(m: ProjectManifest): string | null {
  const detail = m.stage_detail?.analysis as { output_dir?: string } | undefined;
  return detail?.output_dir ?? null;
}
