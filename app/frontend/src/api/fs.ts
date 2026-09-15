import { http } from "./client";

export interface FsRoot { label: string; path: string }
export interface FsEntry { name: string; path: string; is_dir?: boolean; size?: number; is_empty: boolean }
export interface FsListing { path: string; parent: string | null; roots: FsRoot[]; entries: FsEntry[] }

export const fsApi = {
  list: (path?: string, includeFiles = false) =>
    http.get<FsListing>(
      `/api/fs/list?${path ? `path=${encodeURIComponent(path)}&` : ""}files=${includeFiles ? 1 : 0}`),
  mkdir: (parent: string, name: string) =>
    http.post<{ path: string; created: boolean }>("/api/fs/mkdir", { parent, name }),
  suggestOutput: (projectId: string) =>
    http.get<{ path: string }>(`/api/fs/suggest-output?project_id=${encodeURIComponent(projectId)}`)
      .then((r) => r.path),
};
