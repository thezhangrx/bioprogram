import { http } from "./client";

export interface MappingItem {
  scope: "channel" | "sequence";
  channel: string | null;
  symbol: string;
  n_samples_with_symbol: number;
  ambiguous: boolean;
  default_value: number;
  options: { value: number; label: string }[];
  decision: number | null;
}

export interface DatasetInspection {
  schema: string;
  inputs: string[];
  files: { file: string; rows_sampled: number; columns: number; cell_line: string | null; channels: string[] }[];
  cell_lines: string[];
  channels: string[];
  sequence_column: string | null;
  label_column: string | null;
  sequence_length: number;
  symbols: Record<string, Record<string, number>>;
  mapping_items: MappingItem[];
  pending_mapping: number;
  requires_mapping: boolean;
}

export const datasetApi = {
  inspect: (paths: string[]) => http.post<DatasetInspection>("/api/dataset/inspect", { paths }),
  mappingConfig: (payload: {
    inspection: DatasetInspection;
    decisions?: Record<string, number>;
    project_id?: string;
    base_config?: string;
  }) => http.post<{ config_path: string; config: Record<string, unknown> }>(
    "/api/dataset/mapping-config", payload),
};
