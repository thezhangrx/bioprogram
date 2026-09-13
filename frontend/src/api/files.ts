import { http } from "./client";

export interface FileEntry {
  name: string;
  path: string;
  kind: "dir" | "text" | "image" | "binary";
  is_dir: boolean;
  size: number;
  mtime: number;
}

export interface FileListing {
  path: string;
  parent: string | null;
  entries: FileEntry[];
  truncated?: boolean;
}

export interface FilePreview {
  path: string;
  name: string;
  kind: "text" | "image" | "binary" | "dir";
  size: number;
  mtime: number;
  text?: string;
  truncated?: boolean;
  json?: unknown;
  columns?: string[];
  rows?: string[][];
  data_rows?: number;
  row_limit?: number;
  raw_path?: string;
  note?: string;
}

const q = (p: string) => `path=${encodeURIComponent(p)}`;

export const filesApi = {
  list: (path = ".") => http.get<FileListing>(`/api/files?${q(path)}`),
  preview: (path: string) => http.get<FilePreview>(`/api/file-preview?${q(path)}`),
  rawUrl: (path: string) => `/api/file-raw?${q(path)}`,
};
