// Interactive Scientific Discovery Report — 数据契约 (由 Report Data Adapter 填充)。
// 边界: 前端只读 CSV / Markdown / JSON artifact, 不做任何统计判定 (FDR/SNR/tier/CI 全部来自后端)。

export type ReportSectionId =
  | "overview" | "dataset" | "prediction" | "environment" | "sequence"
  | "cellline" | "evidence" | "hypotheses" | "provenance";

export type SectionState = "completed" | "partial" | "skipped" | "unavailable" | "not_selected" | "pending";

export interface SectionStatus {
  id: ReportSectionId;
  title: string;
  state: SectionState;
  detail: string;
  tasks: TaskStatus[];
  artifacts: string[];
}

export interface TaskStatus {
  taskId: string;
  selected: boolean;
  available: boolean;
  status: string;
  reason: string;
  artifact: string;
}

export interface TableData {
  path: string;
  columns: string[];
  rows: Record<string, string>[];
  totalRows?: number;
  truncated?: boolean;
  missing?: boolean;
}

export interface KeyFinding {
  id: string;
  headline: string;          // 只使用 "associated with / candidate / suggests" 等措辞
  detail: string;
  strength?: string;         // 直接来自 artifact 的 evidence_tier / evidence_strength / verdict
  metrics: { label: string; value: string }[];
  sources: string[];         // artifact 路径 (可点击查看)
  section: ReportSectionId;
}

export interface EvidenceCardData {
  feature: string;
  featureType: string;
  tier: string;
  effect: number | null;
  ciLow: number | null;
  ciHigh: number | null;
  ciExcludesZero: boolean | null;
  coverage: string;
  concordance: number | null;
  cellLineConsistency: string;
  permutationP: number | null;
  permutationFdr: number | null;
  models: string[];
  source: string;
}

export interface ScopeEntry { label: string; value: string; included?: boolean }

export interface ReportData {
  outputDir: string;
  batch: string;
  engineVersion: string;
  plan: Record<string, unknown> | null;
  tasks: TaskStatus[];
  sections: SectionStatus[];
  scope: ScopeEntry[];
  findings: KeyFinding[];
  evidenceCards: EvidenceCardData[];
  tables: Record<string, TableData>;
  markdown: Record<string, string>;
  figures: { path: string; name: string; group: string }[];
  provenance: { label: string; value: string }[];
  warnings: string[];
}
