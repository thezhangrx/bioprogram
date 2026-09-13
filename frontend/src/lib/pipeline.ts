import type { PipelineStep } from "../api/pipeline";

/** 步骤类别显示名（与共享编排层 pipeline/steps.py 的 CATEGORY_* 对应）。 */
export const CATEGORY_LABEL: Record<string, string> = {
  data: "Data / 特征",
  train: "Training / 候选",
  analysis: "Analysis / 统计",
  deliverable: "Deliverables / 交付物",
};

export const CATEGORY_ORDER = ["data", "train", "analysis", "deliverable"] as const;

export function groupByCategory(steps: PipelineStep[]): { category: string; steps: PipelineStep[] }[] {
  return CATEGORY_ORDER.map((category) => ({
    category,
    steps: steps.filter((s) => s.category === category),
  })).filter((g) => g.steps.length > 0);
}

/** 步骤是否可运行：依赖已完成（后端 ready）且不是内部检查步骤的空命令。 */
export function canRun(step: PipelineStep): boolean {
  return step.ready && step.kind !== "internal";
}

/** 运行前提示文案：重任务会真实写入 models/results/logs。 */
export function confirmText(step: PipelineStep): string {
  if (step.kind === "internal") return `执行交付物核对「${step.title}」？`;
  if (step.heavy) {
    return `「${step.title}」是重任务：会真实训练/推理并写入 models/、results/、logs/。确认执行？`;
  }
  return `执行「${step.title}」？会写入 results/ 下的分析产物。`;
}

export function statusTone(status: string): "ok" | "run" | "warn" | "idle" {
  if (status === "completed") return "ok";
  if (status === "running") return "run";
  if (status === "partial" || status === "failed") return "warn";
  return "idle";
}

export function artifactLabel(a: { rel: string; exists: boolean }): string {
  return `${a.exists ? "✓" : "✗"} ${a.rel}`;
}
