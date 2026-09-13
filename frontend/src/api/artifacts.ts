import { http } from "./client";
import type { ArtifactKind, CsvPayload, TextPayload } from "../types";

export interface ArtifactResult {
  kind: ArtifactKind;
  path: string;
  name: string;
  size: number;
  columns?: string[];
  rows?: string[][];
  type_hints?: string[];
  data_rows?: number;
  truncated?: boolean;
  text?: string;
  json?: unknown;
  error?: string;
}

export const artifactApi = {
  get: (path: string) =>
    http.get<ArtifactResult>(`/api/artifacts?path=${encodeURIComponent(path)}`),
  page: (path: string, offset: number, limit: number) =>
    http.get<ArtifactResult>(`/api/artifacts?path=${encodeURIComponent(path)}&offset=${offset}&limit=${limit}`),
  asCsv: async (path: string): Promise<CsvPayload> => {
    const r = await artifactApi.get(path);
    if (r.kind !== "csv" || !r.columns || !r.rows) {
      throw new Error(`not a csv artifact: ${r.kind}`);
    }
    return r as unknown as CsvPayload;
  },
  asMarkdown: async (path: string): Promise<TextPayload> => {
    const r = await artifactApi.get(path);
    if (r.kind !== "md" && r.kind !== "txt") throw new Error(`not markdown: ${r.kind}`);
    return r as unknown as TextPayload;
  },
  rawUrl: (path: string) => `/api/artifact-raw?path=${encodeURIComponent(path)}`,
};
