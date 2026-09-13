import { http } from "./client";

// 注意：后端分析引擎沿用 batch_dir 作为"结果目录"参数名（引擎内部词汇）；
// 前端用户界面不再暴露 batch 概念，传入的是 Cell 01 选择的绝对输出目录下的 results/。
export interface AnalysisTask {
  task_id: string;
  display: string;
  category: string;
  dependencies: string[];
  available?: boolean | null;
  reason?: string;
}

export interface AnalysisRunManifest {
  status: string;
  batch_dir: string;
  output_dir: string;
  selected_tasks: string[];
  pid?: number;
  started_at?: string;
}

export interface EngineTaskState {
  task_id: string;
  status: string;
  reason?: string;
}

export const analysisApi = {
  tasks: (resultsDir?: string) =>
    http.get<{ tasks: AnalysisTask[] }>(
      `/api/analysis/tasks${resultsDir ? `?batch=${encodeURIComponent(resultsDir)}` : ""}`).then((r) => r.tasks),
  plan: (selected: string[]) =>
    http.post<{ plan: Record<string, unknown> }>("/api/analysis/plan", { selected_tasks: selected }),
  run: (batchDir: string, selected: string[], projectId?: string) =>
    http.post<AnalysisRunManifest>("/api/analysis/run", {
      batch_dir: batchDir,
      selected_tasks: selected,
      project_id: projectId,
    }),
  status: (outputDir: string) =>
    http.get<{ status: string; engine_status?: { tasks?: EngineTaskState[] }; task_status?: Record<string, string> }>(
      `/api/analysis/status?output_dir=${encodeURIComponent(outputDir)}`),
};

export interface AnalysisOutputEntry { name: string; path: string; kind: string }
export const analysisApiOutputs = {
  list: (outputDir: string) =>
    http.get<{ output_dir: string; entries: AnalysisOutputEntry[] }>(
      `/api/analysis/outputs?output_dir=${encodeURIComponent(outputDir)}`),
};
