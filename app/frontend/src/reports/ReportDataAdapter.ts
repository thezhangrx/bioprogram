// Report Data Adapter — 唯一的数据访问层。
//
// 结构: Artifacts (CSV/MD/JSON/PNG) -> ReportData -> Report Sections。
// Section 组件**不得**自己读取文件; 也不得复制任何统计规则 (FDR/SNR/tier/CI 判定全部来自后端 artifact)。
// 依赖以参数注入, 便于单元测试 (不访问网络)。

import { boolLabel, directionLabel } from "../lib/labels";
import type {
  EvidenceCardData, KeyFinding, ReportData, ReportSectionId, SectionState, SectionStatus,
  ScopeEntry, TableData, TaskStatus,
} from "./types";

export interface ReportAdapterDeps {
  listOutputs(outputDir: string): Promise<{ name: string; path: string; kind: string }[]>;
  getStatus(outputDir: string): Promise<Record<string, unknown>>;
  getTable(path: string, base: string): Promise<TableData>;
  getText(path: string, base: string): Promise<string>;
}

const TABLE_FILES: Record<string, string> = {
  experimentTable: "tables/experiment_table.csv",
  prediction: "tables/prediction_summary.csv",
  loco: "tables/loco_performance.csv",
  conditional: "tables/environment_conditional_delta_r2.csv",
  mainEffects: "tables/environment_main_effects.csv",
  edges: "tables/environment_edges.csv",
  nodes: "tables/environment_nodes.csv",
  bootstrap: "tables/bootstrap_results.csv",
  permutation: "tables/permutation_results.csv",
  anova: "tables/anova_results.csv",
  evidence: "tables/evidence_matrix.csv",
  cellline: "tables/cellline_effects.csv",
  motifs: "tables/motif_candidates.csv",
  motifEnrichment: "tables/motif_enrichment.csv",
  motifConsistency: "tables/motif_consistency.csv",
  attribution: "tables/attribution_summary.csv",
  importance: "tables/importance_vs_delta_r2.csv",
};

const MD_FILES: Record<string, string> = {
  overview: "reports/00_overview.md",
  dataQuality: "reports/01_data_quality.md",
  prediction: "reports/02_prediction_generalization.md",
  environment: "reports/03_environment_effects.md",
  sequenceMotifs: "reports/04_sequence_and_motifs.md",
  cellline: "reports/05_cellline_heterogeneity.md",
  evidence: "reports/06_evidence_integration.md",
  hypotheses: "reports/07_biological_hypotheses.md",
  anomaly: "reports/08_anomaly_report.md",
};

const SECTION_TASKS: Record<ReportSectionId, string[]> = {
  overview: ["qc", "prediction"],
  dataset: ["qc"],
  prediction: ["prediction"],
  environment: ["environment_conditional_effect", "environment_main_effect",
    "environment_factorial_dag", "environment_anova", "bootstrap", "hypothesis_testing",
    "fdr_correction"],
  sequence: ["sequence_attribution", "cnn_ism", "motif_discovery", "motif_enrichment"],
  cellline: ["cellline_heterogeneity"],
  evidence: ["evidence_integration"],
  hypotheses: ["hypothesis_generation"],
  provenance: [],
};

const SECTION_TITLES: Record<ReportSectionId, string> = {
  overview: "总览与关键发现",
  dataset: "数据集与质量",
  prediction: "预测与泛化",
  environment: "环境因素",
  sequence: "序列与候选模式",
  cellline: "细胞系背景",
  evidence: "证据整合",
  hypotheses: "生物学假设",
  provenance: "可复现性与溯源",
};

// ---------------------------------------------------------------- helpers

export function num(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

export function fmt(value: number | null, digits = 4): string {
  if (value === null) return "NA";
  return value.toFixed(digits);
}

export function fmtSigned(value: number | null, digits = 4): string {
  if (value === null) return "NA";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

/** 任务状态 -> section 状态 (不使用任何科学判定, 只做状态聚合)。 */
export function sectionState(tasks: TaskStatus[]): SectionState {
  if (!tasks.length) return "completed";
  const selected = tasks.filter((t) => t.selected);
  if (!selected.length) return "not_selected";
  const statuses = selected.map((t) => t.status);
  if (statuses.some((s) => s === "completed")) {
    return statuses.every((s) => s === "completed") ? "completed" : "partial";
  }
  if (statuses.every((s) => s === "skipped")) {
    const reasons = selected.map((t) => t.reason || "");
    return reasons.some((r) => r.includes("user_disabled")) ? "not_selected" : "skipped";
  }
  if (statuses.some((s) => s === "unavailable")) return "unavailable";
  if (statuses.some((s) => s === "failed")) return "unavailable";
  return "pending";
}

export const STATE_LABEL: Record<SectionState, string> = {
  completed: "已完成",
  partial: "部分完成",
  skipped: "已跳过",
  unavailable: "不可用",
  not_selected: "未在分析方案中选取",
  pending: "待处理",
};

export function taskStatuses(raw: unknown, artifacts: Record<string, string> = {}): TaskStatus[] {
  const list = Array.isArray(raw) ? raw : [];
  return list.map((t) => {
    const rec = (t ?? {}) as Record<string, unknown>;
    const taskId = String(rec.task_id ?? "");
    return {
      taskId,
      selected: rec.selected === undefined ? true : Boolean(rec.selected),
      available: rec.available === undefined ? true : Boolean(rec.available),
      status: String(rec.status ?? "pending"),
      reason: String(rec.reason ?? ""),
      artifact: String(rec.artifact ?? artifacts[taskId] ?? ""),
    };
  });
}

/** 从 00_overview.md 的 bullet 行读出数据集规模 (不硬编码任何项目数字)。 */
export function parseOverviewScope(md: string): ScopeEntry[] {
  const out: ScopeEntry[] = [];
  for (const line of md.split("\n")) {
    const m = line.match(/^-\s*([^:]+):\s*(.+)$/);
    if (m) out.push({ label: m[1].trim(), value: m[2].replace(/\*\*/g, "").trim() });
  }
  return out;
}

export function parseAnalysisScope(tasks: TaskStatus[]): ScopeEntry[] {
  const wanted = ["bootstrap", "hypothesis_testing", "environment_anova",
    "motif_discovery", "motif_enrichment", "fdr_correction", "environment_factorial_dag"];
  return wanted.map((id) => {
    const t = tasks.find((x) => x.taskId === id);
    return {
      label: id,
      value: t ? t.status : "本次构建中无此任务",
      included: t ? t.selected && t.status === "completed" : false,
    };
  });
}

// ---------------------------------------------------------------- findings

export function buildFindings(data: {
  evidence?: TableData; motifs?: TableData; prediction?: TableData; edges?: TableData;
}): KeyFinding[] {
  const findings: KeyFinding[] = [];
  const ev = data.evidence;
  const envRows = ev && !ev.missing
    ? ev.rows.filter((r) => (r.feature_type ?? "environment") !== "motif") : [];
  const tierOrder = (tier: string) =>
    tier.includes("Tier 1") ? 0 : tier.includes("Tier 2") ? 1 : tier.includes("Tier 3") ? 2 : 3;
  const strongest = [...envRows].sort((a, b) => tierOrder(String(a.evidence_tier)) -
    tierOrder(String(b.evidence_tier))).slice(0, 3);
  for (const row of strongest) {
    const tier = String(row.evidence_tier ?? "");
    if (!tier || tier.includes("Inconclusive")) continue;
    const ci = row.ci_excludes_zero;
    findings.push({
      id: `evidence-${row.feature}`,
      headline: `${row.feature} 是与编辑效率相关的候选环境因素。`,
      detail: `综合 ${row.coverage ?? "?"} 个适用模型；`
        + `方向一致率 ${fmt(num(row.direction_concordance), 2)}；`
        + `细胞系一致性：${row.cell_line_consistency ?? "NA"}。`,
      strength: tier,
      metrics: [
        { label: "总体 ΔR²", value: fmtSigned(num(row.overall_effect)) },
        { label: "95% CI", value: row.ci_low ? `[${fmt(num(row.ci_low))}, ${fmt(num(row.ci_high))}]` : "NA" },
        { label: "置信区间不含 0", value: boolLabel(ci) },
        { label: "置换检验 FDR", value: fmt(num(row.permutation_fdr)) },
      ],
      sources: [data.evidence?.path, data.edges?.path].filter(Boolean) as string[],
      section: "environment",
    });
  }

  const motifRows = data.motifs && !data.motifs.missing ? data.motifs.rows : [];
  const strongMotifs = motifRows.filter((m) =>
    String(m.evidence_strength ?? "").startsWith("Strong")
    || String(m.evidence_strength ?? "").startsWith("Moderate")).slice(0, 3);
  for (const m of strongMotifs) {
    findings.push({
      id: `motif-${m.motif_id}`,
      headline: `候选模式 ${m.human_pattern}（IUPAC ${m.iupac}）是与编辑效率相关的候选序列模式。`,
      detail: `归因提取的 seqlet：${m.support_count} 个实例 / ${m.sample_support} 个样本；`
        + `方向：${directionLabel(m.effect_direction)}（来源：${m.direction_source ?? "NA"}）。`,
      strength: String(m.evidence_strength ?? ""),
      metrics: [
        { label: "平均效应", value: fmtSigned(num(m.mean_effect)) },
        { label: "富集 (FDR)", value: m.FDR ? `${fmt(num(m.enrichment), 3)} (${fmt(num(m.FDR), 4)})` : "未执行" },
        { label: "正则", value: String(m.regex ?? "NA") },
        { label: "长度", value: String(m.length ?? "NA") },
      ],
      sources: [data.motifs?.path ?? ""].filter(Boolean),
      section: "sequence",
    });
  }

  const predRows = data.prediction && !data.prediction.missing ? data.prediction.rows : [];
  if (predRows.length) {
    const best = [...predRows].sort((a, b) => (num(b.R2) ?? -Infinity) - (num(a.R2) ?? -Infinity))[0];
    findings.push({
      id: "prediction-best",
      headline: "模型预测性能仅作性能报告，不代表生物学重要性。",
      detail: `最佳配置：${best.model ?? "?"} / ${best.split_type ?? "?"} / `
        + `${best.cell_line ?? "?"}。预测性能与因素发现证据严格分开。`,
      strength: "预测性能（不属于因素证据）",
      metrics: [
        { label: "R²", value: fmt(num(best.R2)) },
        { label: "RMSE", value: fmt(num(best.RMSE)) },
        { label: "MAE", value: fmt(num(best.MAE)) },
        { label: "Spearman", value: fmt(num(best.Spearman)) },
      ],
      sources: [data.prediction?.path ?? ""].filter(Boolean),
      section: "prediction",
    });
  }
  return findings;
}

export function buildEvidenceCards(table: TableData | undefined): EvidenceCardData[] {
  if (!table || table.missing) return [];
  return table.rows
    .filter((r) => (r.feature_type ?? "environment") !== "motif")
    .map((r) => ({
      feature: String(r.feature ?? ""),
      featureType: String(r.feature_type ?? "environment"),
      tier: String(r.evidence_tier ?? ""),
      effect: num(r.overall_effect),
      ciLow: num(r.ci_low),
      ciHigh: num(r.ci_high),
      ciExcludesZero: r.ci_excludes_zero === "" || r.ci_excludes_zero === undefined
        ? null : String(r.ci_excludes_zero).toLowerCase() === "true",
      coverage: String(r.coverage ?? "NA"),
      concordance: num(r.direction_concordance),
      cellLineConsistency: String(r.cell_line_consistency ?? "NA"),
      permutationP: num(r.permutation_p),
      permutationFdr: num(r.permutation_fdr),
      models: String(r.applicable_models ?? "").split(";").filter(Boolean),
      source: table.path,
    }));
}

// ---------------------------------------------------------------- adapter

export async function buildReportData(outputDir: string,
                                     deps: ReportAdapterDeps): Promise<ReportData> {
  const warnings: string[] = [];
  const entries = await deps.listOutputs(outputDir).catch(() => []);
  const status = await deps.getStatus(outputDir).catch(() => ({} as Record<string, unknown>));

  const engine = (status.engine_status ?? {}) as Record<string, unknown>;
  const rawTasks = (engine.tasks ?? status.tasks ?? []) as unknown[];
  const artifactMap: Record<string, string> = {};
  for (const t of rawTasks) {
    const rec = t as Record<string, unknown>;
    if (rec.task_id && rec.artifact) artifactMap[String(rec.task_id)] = String(rec.artifact);
  }
  const tasks = taskStatuses(rawTasks, artifactMap);

  const tables: Record<string, TableData> = {};
  for (const [key, rel] of Object.entries(TABLE_FILES)) {
    try {
      tables[key] = await deps.getTable(rel, outputDir);
    } catch {
      tables[key] = { path: rel, columns: [], rows: [], missing: true };
      warnings.push(`产物不可用：${rel}`);
    }
  }
  const markdown: Record<string, string> = {};
  for (const [key, rel] of Object.entries(MD_FILES)) {
    // 新布局 <out>/reports/；兼容旧布局 <out>/summary/
    const candidates = [rel, rel.replace(/^reports\//, "summary/")];
    markdown[key] = "";
    for (const cand of candidates) {
      try {
        markdown[key] = await deps.getText(cand, outputDir);
        break;
      } catch {
        /* 尝试下一个布局 */
      }
    }
  }

  const figures = entries.filter((e) => e.kind === "png" || e.name.endsWith(".png"))
    .map((e) => ({
      path: e.path, name: e.name,
      group: e.path.includes("/") ? e.path.split("/").slice(-2)[0] : "figures",
    }));

  const sections: SectionStatus[] = (Object.keys(SECTION_TASKS) as ReportSectionId[]).map((id) => {
    const taskIds = SECTION_TASKS[id];
    const secTasks = tasks.filter((t) => taskIds.includes(t.taskId));
    const state = taskIds.length ? sectionState(secTasks) : "completed";
    const artifacts: string[] = [];
    for (const t of secTasks) if (t.artifact) artifacts.push(t.artifact);
    if (id === "sequence") artifacts.push("tables/motif_candidates.csv");
    if (id === "dataset") artifacts.push("reports/01_data_quality.md");
    return {
      id, title: SECTION_TITLES[id], state,
      detail: secTasks.map((t) => `${t.taskId}: ${t.status}${t.reason ? ` (${t.reason})` : ""}`)
        .join("; ") || "本节未绑定分析任务",
      tasks: secTasks,
      artifacts: Array.from(new Set(artifacts)),
    };
  });

  const scope = [
    ...parseOverviewScope(markdown.overview ?? ""),
    ...parseAnalysisScope(tasks),
  ];

  const provenance = [
    { label: "output_dir", value: outputDir },
    { label: "batch", value: String(status.batch ?? engine.batch ?? "") },
    { label: "engine_version", value: String(status.engine_version ?? engine.engine_version ?? "") },
    { label: "analysis_plan", value: status.plan ? JSON.stringify(status.plan) : "见 analysis_plan.json" },
    { label: "started_at", value: String(engine.started_at ?? "") },
    { label: "completed_at", value: String(engine.completed_at ?? "") },
    { label: "figures", value: String(figures.length) },
    { label: "tables", value: String(Object.values(tables).filter((t) => !t.missing).length) },
  ];

  return {
    outputDir,
    batch: String(status.batch ?? ""),
    engineVersion: String(status.engine_version ?? ""),
    plan: (status.plan as Record<string, unknown>) ?? null,
    tasks,
    sections,
    scope,
    findings: buildFindings({ evidence: tables.evidence, motifs: tables.motifs,
      prediction: tables.prediction, edges: tables.edges }),
    evidenceCards: buildEvidenceCards(tables.evidence),
    tables,
    markdown,
    figures,
    provenance,
    warnings,
  };
}

/** 真实环境下的依赖实现 (浏览器)。 */
export function httpDeps(): ReportAdapterDeps {
  return {
    listOutputs: async (outputDir) => {
      const r = await fetch(`/api/analysis/outputs?output_dir=${encodeURIComponent(outputDir)}`);
      if (!r.ok) throw new Error(`产物列表请求失败：${r.status}`);
      const j = await r.json();
      return (j.entries ?? []) as { name: string; path: string; kind: string }[];
    },
    getStatus: async (outputDir) => {
      const r = await fetch(`/api/analysis/status?output_dir=${encodeURIComponent(outputDir)}`);
      if (!r.ok) throw new Error(`状态请求失败：${r.status}`);
      return (await r.json()) as Record<string, unknown>;
    },
    getTable: async (path, base) => {
      const r = await fetch(`/api/artifacts?path=${encodeURIComponent(path)}`
        + `&base=${encodeURIComponent(base)}`);
      if (!r.ok) throw new Error(`产物请求失败：${r.status}`);
      const j = await r.json();
      const columns: string[] = j.columns ?? [];
      const rows: Record<string, string>[] = (j.rows ?? []).map((row: string[]) => {
        const obj: Record<string, string> = {};
        columns.forEach((c, i) => { obj[c] = row[i]; });
        return obj;
      });
      return { path, columns, rows, totalRows: j.data_rows, truncated: j.truncated };
    },
    getText: async (path, base) => {
      const r = await fetch(`/api/artifacts?path=${encodeURIComponent(path)}`
        + `&base=${encodeURIComponent(base)}`);
      if (!r.ok) throw new Error(`产物请求失败：${r.status}`);
      const j = await r.json();
      return String(j.text ?? "");
    },
  };
}
