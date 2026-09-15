import { http } from "./client";
import type { ProjectManifest } from "../types";

export interface ProjectConfigPatch {
  name?: string;                 // 修改项目名（不再是 batch）
  output_dir?: string;           // 绝对输出目录（results/models/logs 在其下派生）
  data_dir?: string;
  target_paths?: string[];
  feature_config?: string;
  mapping_decisions?: Record<string, number>;
  inspection_summary?: Record<string, unknown>;
  device?: string;
  models?: string[];
  cell_lines?: string[];
  split_types?: string[];
  scope_epi?: string[];
}

export interface DeleteResult {
  deleted: string;
  name?: string;
  removed: { path: string; bytes: number }[];
  skipped: { path: string; reason: string }[];
  freed_bytes: number;
}

export const projectApi = {
  list: () => http.get<{ projects: ProjectManifest[] }>("/api/projects").then((r) => r.projects),
  create: (name: string, datasetPaths: string[]) =>
    http.post<ProjectManifest>("/api/projects", { name, dataset_paths: datasetPaths }),
  open: (id: string) => http.get<ProjectManifest>(`/api/projects/${id}`),
  updateStage: (id: string, stage: string, status: string, detail?: Record<string, unknown>) =>
    http.post<ProjectManifest>(`/api/projects/${id}/stage`, { stage, status, detail }),
  remove: (id: string, force = false) =>
    http.del<DeleteResult>(`/api/projects/${id}${force ? "?force=1" : ""}`),
  updateConfig: (id: string, config: ProjectConfigPatch) =>
    http.post<ProjectManifest>(`/api/projects/${id}/config`, { config }),
  fromQc: (sessionId: string, name: string) =>
    http.post<ProjectManifest>("/api/projects/from-qc", { session_id: sessionId, name }),
};
