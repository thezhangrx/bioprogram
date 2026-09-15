import { http } from "./client";
import type { RunManifest } from "./training";

export interface StepArtifact { rel: string; path: string; exists: boolean; size?: number }

export interface PipelineStep {
  schema: string;
  step_id: string;
  title: string;
  category: "data" | "train" | "analysis" | "deliverable";
  heavy: boolean;
  requires: string[];
  description: string;
  kind: "subprocess" | "internal";
  artifacts: StepArtifact[];
  command: string;
  status: "completed" | "partial" | "pending";
  ready: boolean;
}

export interface PipelineStepsPayload {
  schema: string;
  context: Record<string, unknown>;      // 全绝对路径：output_dir/results_dir/model_dir/logs_dir/data_dir
  output_dir: string;
  results_dir: string;
  order: string[];
  steps: PipelineStep[];
}

export interface PipelineRunOptions {
  dry_run?: boolean;
  output_dir?: string;
  options?: Record<string, unknown>;
  /** 允许透传后端白名单内的上下文字段（results_dir / data_dir / feature_config ...） */
  [key: string]: unknown;
}

export interface PipelineRunResult extends Partial<Omit<RunManifest, "run_id">> {
  step_id?: string;
  kind: string;
  status: string;
  run_id?: string | null;
  checks?: { artifact: string; path: string; exists: boolean }[];
  message?: string;
}

export const pipelineApi = {
  steps: (outputDir?: string) =>
    http.get<PipelineStepsPayload>(
      `/api/pipeline/steps${outputDir ? `?output_dir=${encodeURIComponent(outputDir)}` : ""}`),
  run: (stepId: string, opts: PipelineRunOptions = {}) =>
    http.post<PipelineRunResult>("/api/pipeline/run", { step_id: stepId, ...opts }),
};
