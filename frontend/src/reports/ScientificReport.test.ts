// Interactive Scientific Discovery Report — adapter / 数据层测试。
//
// 证明: (a) 只消费 artifact; (b) 状态聚合与 AnalysisPlan 一致; (c) 不复制统计规则;
// (d) 缺 artifact 时不伪造 (显示 Unavailable / NA)。

import { describe, expect, it } from "vitest";
import {
  buildEvidenceCards, buildFindings, buildReportData, parseAnalysisScope, parseOverviewScope,
  sectionState, taskStatuses, type ReportAdapterDeps,
} from "./ReportDataAdapter";
import type { TableData } from "./types";

const table = (path: string, rows: Record<string, string>[]): TableData =>
  ({ path, columns: Object.keys(rows[0] ?? {}), rows });

const evidenceTable = table("tables/evidence_matrix.csv", [
  { feature: "ctcf", feature_type: "environment", overall_effect: "0.0031", ci_low: "0.001",
    ci_high: "0.005", ci_excludes_zero: "True", coverage: "7",
    direction_concordance: "0.857", cell_line_consistency: "Context-conflicting",
    permutation_fdr: "0.002", permutation_p: "0.001",
    applicable_models: "linear;mlp", evidence_tier: "Tier 2: Moderate convergent evidence" },
  { feature: "rrbs", feature_type: "environment", overall_effect: "-0.0004", ci_low: "-0.002",
    ci_high: "0.001", ci_excludes_zero: "False", coverage: "7",
    direction_concordance: "0.71", cell_line_consistency: "Context-conflicting",
    permutation_fdr: "0.4", evidence_tier: "Inconclusive" },
]);

const motifTable = table("tables/motif_candidates.csv", [
  { motif_id: "motif_cnn33_hela_all_cnn_ism_001", human_pattern: "CTGG", iupac: "CTGG",
    regex: "CTGG", length: "4", support_count: "1167", sample_support: "1167",
    effect_direction: "-", mean_effect: "-0.038", FDR: "0.01", enrichment: "1.4",
    evidence_strength: "Moderate motif evidence", direction_source: "carrier_vs_background_measured_efficacy" },
]);

function deps(overrides: Partial<ReportAdapterDeps> = {}): ReportAdapterDeps {
  return {
    listOutputs: async () => ([
      { name: "00_overview.md", path: "summary/00_overview.md", kind: "md" },
      { name: "factorial_dag", path: "figures/03_environment/factorial_dag", kind: "dir" },
      { name: "x.png", path: "figures/03_environment/factorial_dag/x.png", kind: "png" },
    ]),
    getStatus: async () => ({
      status: "completed",
      batch: "batch_x",
      engine_version: "1.0",
      engine_status: {
        started_at: "t0", completed_at: "t1",
        tasks: [
          { task_id: "qc", selected: true, available: true, status: "completed",
            artifact: "summary/01_data_quality.md", reason: "" },
          { task_id: "bootstrap", selected: true, available: true, status: "completed",
            artifact: "tables/bootstrap_results.csv", reason: "" },
          { task_id: "environment_anova", selected: false, available: true, status: "skipped",
            artifact: "tables/anova_results.csv", reason: "user_disabled" },
          { task_id: "motif_enrichment", selected: true, available: false, status: "unavailable",
            artifact: "tables/motif_enrichment.csv", reason: "insufficient_data" },
        ],
      },
    }),
    getTable: async (path) => {
      if (path.includes("evidence_matrix")) return evidenceTable;
      if (path.includes("motif_candidates")) return motifTable;
      if (path.includes("prediction_summary")) {
        return table(path, [{ model: "xgboost", split_type: "single", cell_line: "hct116",
          R2: "0.19", RMSE: "0.16", MAE: "0.13", Spearman: "0.32" }]);
      }
      throw new Error("not found");
    },
    getText: async (path) => path.endsWith("00_overview.md")
      ? "- experiment count: **1344**\n- models: a, b\n" : "",
    ...overrides,
  };
}

describe("ReportDataAdapter", () => {
  it("loads artifact-backed sections and marks missing tables as unavailable", async () => {
    const data = await buildReportData("/out", deps());
    expect(data.batch).toBe("batch_x");
    expect(data.tables.evidence.rows).toHaveLength(2);
    expect(data.tables.loco.missing).toBe(true);              // 缺 artifact -> 不伪造
    expect(data.warnings.some((w) => w.includes("loco_performance"))).toBe(true);
    expect(data.figures).toHaveLength(1);
  });

  it("keeps section status consistent with the AnalysisPlan selection", async () => {
    const data = await buildReportData("/out", deps());
    const byId = Object.fromEntries(data.sections.map((s) => [s.id, s]));
    expect(byId.overview.state).toBe("completed");
    // anova 未选择不应让整个章节降级 (不是 "partial"), 但 detail 必须如实说明
    expect(byId.environment.state).toBe("completed");
    expect(byId.environment.detail).toContain("environment_anova: skipped");
    // 章节内被选择的任务不可用 -> unavailable (不假装完成)
    expect(byId.sequence.state).toBe("unavailable");
  });

  it("marks a section partial when a selected task is unavailable", async () => {
    const data = await buildReportData("/out", deps({
      getStatus: async () => ({
        status: "completed", batch: "batch_x", engine_version: "1.0",
        engine_status: { tasks: [
          { task_id: "bootstrap", selected: true, available: true, status: "completed",
            artifact: "tables/bootstrap_results.csv", reason: "" },
          { task_id: "fdr_correction", selected: true, available: false, status: "unavailable",
            artifact: "tables/permutation_results.csv",
            reason: "no corrigible p-value family available in this batch" },
        ] },
      }),
    }));
    const env = data.sections.find((s) => s.id === "environment");
    expect(env?.state).toBe("partial");
  });

  it("derives findings only from backend labels (no frontend statistics)", async () => {
    const data = await buildReportData("/out", deps());
    const headlines = data.findings.map((f) => f.headline).join(" ");
    expect(headlines).toContain("candidate");
    expect(headlines).not.toMatch(/causes|proves|determines/);
    const envFinding = data.findings.find((f) => f.id === "evidence-ctcf");
    expect(envFinding?.strength).toBe("Tier 2: Moderate convergent evidence");
    expect(envFinding?.metrics.find((m) => m.label === "CI excludes 0")?.value).toBe("True");
    // 不因为 ΔR² 为正就声称显著性; 只用后端 tier 标签
    const inconclusive = data.findings.find((f) => f.id === "evidence-rrbs");
    expect(inconclusive).toBeUndefined();
  });

  it("maps evidence cards without recomputing anything", () => {
    const cards = buildEvidenceCards(evidenceTable);
    expect(cards).toHaveLength(2);
    expect(cards[0].ciExcludesZero).toBe(true);
    expect(cards[0].models).toEqual(["linear", "mlp"]);
    expect(cards[1].ciExcludesZero).toBe(false);
  });

  it("handles empty artifacts without fabricating findings", () => {
    expect(buildFindings({})).toEqual([]);
    const empty = table("tables/motif_candidates.csv", []);
    expect(buildFindings({ motifs: empty })).toEqual([]);
  });

  it("parses dataset scope from the overview markdown", () => {
    const scope = parseOverviewScope("- experiment count: **1344**\n- models: a, b\nnoise\n");
    expect(scope).toEqual([
      { label: "experiment count", value: "1344" },
      { label: "models", value: "a, b" },
    ]);
  });

  it("reports analysis scope from task statuses", () => {
    const tasks = taskStatuses([
      { task_id: "bootstrap", status: "completed", selected: true, available: true },
      { task_id: "environment_anova", status: "skipped", selected: false, available: true },
    ]);
    const scope = parseAnalysisScope(tasks);
    expect(scope.find((s) => s.label === "bootstrap")?.included).toBe(true);
    expect(scope.find((s) => s.label === "environment_anova")?.included).toBe(false);
    expect(scope.find((s) => s.label === "motif_enrichment")?.value).toBe("not in this build");
  });
});

describe("sectionState", () => {
  const task = (status: string, selected = true, reason = "") =>
    ({ taskId: "t", selected, available: true, status, reason, artifact: "" });

  it("distinguishes user_disabled from insufficient data", () => {
    expect(sectionState([task("skipped", false, "user_disabled")])).toBe("not_selected");
    expect(sectionState([task("skipped", true, "insufficient_data: x")])).toBe("skipped");
    expect(sectionState([task("unavailable", true, "insufficient_data")])).toBe("unavailable");
    expect(sectionState([task("completed"), task("completed")])).toBe("completed");
    expect(sectionState([task("completed"), task("unavailable")])).toBe("partial");
  });
});
