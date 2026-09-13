import { http } from "./client";
import type { QcSession } from "../types";

export const qcApi = {
  list: () => http.get<{ sessions: QcSession[] }>("/api/qc/sessions").then((r) => r.sessions),
  start: (inputPaths: string[], note = "") =>
    http.post<QcSession>("/api/qc/sessions", { input_paths: inputPaths, note }),
  get: (id: string) => http.get<QcSession>(`/api/qc/sessions/${id}`),
  reuseCheck: (sessionId: string, inputPaths: string[]) =>
    http.post<{ reusable: boolean; fingerprint: unknown }>("/api/qc/reuse-check", {
      session_id: sessionId,
      input_paths: inputPaths,
    }),
};
