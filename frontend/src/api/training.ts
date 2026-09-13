import { http } from "./client";

export interface TrainingDefaults {
  config: Record<string, unknown>;
  allowed: {
    models: string[];
    cell_lines: string[];
    split_types: string[];
    cnn_kernels: number[];
    mixed_seeds: number[];
    runtimes: string[];
  };
}

export interface PreflightCheck {
  check: string;
  ok: boolean;
  message: string;
}
export interface PreflightResult { ok: boolean; checks: PreflightCheck[] }

export interface RunManifest {
  run_id: string;
  kind: string;
  status: string;
  runtime: string;
  /** 仅调试运行时才有值（命令行 --batch-name）；前端流程恒为空 */
  batch_name: string;
  output_dir?: string;
  started_at?: string;
  pid?: number | null;
  command?: string;
  log_path?: string;
  progress?: { done: number; total: number | null; ratio: number | null };
  error_tail?: string;
  note?: string;
}

export interface DevicePolicy {
  allowed: string[];
  locked: boolean;
  cpu_only: boolean;
  note: string;
}

export const trainingApi = {
  defaults: () => http.get<TrainingDefaults>("/api/training/defaults"),
  devicePolicy: (models: string[]) =>
    http.post<{ policy: DevicePolicy }>("/api/training/device-policy", { models }).then((r) => r.policy),
  preflight: (config: Record<string, unknown>) =>
    http.post<PreflightResult>("/api/training/preflight", { config }),
  submit: (config: Record<string, unknown>) =>
    http.post<RunManifest>("/api/training/submit", { config }),
  runs: () => http.get<{ runs: RunManifest[] }>("/api/runs").then((r) => r.runs),
  status: (id: string) => http.get<RunManifest>(`/api/runs/${id}`),
  cancel: (id: string) => http.post<RunManifest>(`/api/runs/${id}/cancel`),
  resume: (id: string) => http.post<RunManifest>(`/api/runs/${id}/resume`),
  log: (id: string) => http.get<{ lines: string[] }>(`/api/runs/${id}/log`),
};
