// 与后端 crispr_workspace 契约对应的类型 (状态一律来自后端 manifest/status json)
export type StageKey =
  | "data" | "qc" | "mapping" | "training" | "analysis" | "reports";

export type StageStatus =
  | "pending" | "running" | "completed" | "failed" | "skipped" | "unavailable" | "warning";

export const STAGE_ORDER: StageKey[] = [
  "data", "qc", "mapping", "training", "analysis", "reports",
];

export interface Fingerprint {
  algorithm: string;
  digest: string;
  n_files: number;
  total_bytes: number;
  files: { name: string; path: string; size: number; sha256: string }[];
}

export interface ProjectManifest {
  schema: string;
  project_id: string;
  name: string;
  created_at: string;
  updated_at: string;
  dataset: {
    input_paths: string[];
    fingerprint: Fingerprint | null;
    imported: boolean;
  };
  stages: Record<StageKey, StageStatus>;
  stage_detail?: Record<string, Record<string, unknown>>;
  config?: Record<string, unknown>;
  config_versions: Record<string, string | null>;
}

export interface QcSession {
  session_id: string;
  schema: string;
  created_at: string;
  status: "running" | "completed" | "failed";
  dataset?: { fingerprint?: Fingerprint };
  outputs?: { summary?: string; report?: string; figures_dir?: string };
  qc_summary?: Record<string, unknown>;
  figures?: string[];
  returncode?: number;
  stderr_tail?: string;
}

export type ArtifactKind = "csv" | "md" | "txt" | "json" | "image" | "log" | "other";

export interface ArtifactMeta {
  path: string;
  name: string;
  kind: ArtifactKind;
  size: number;
  mtime: number;
}

export interface CsvPayload extends ArtifactMeta {
  kind: "csv";
  columns: string[];
  rows: string[][];
  type_hints: string[];
  total_rows: number;
  data_rows: number;
  truncated: boolean;
  row_limit: number;
}

export interface TextPayload extends ArtifactMeta {
  text: string;
}
