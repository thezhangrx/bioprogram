// 统一 Artifact Viewer: 按文件类型分派 (CSV/Markdown/…), 供 QC/Analysis/Reports/Notebook 共用。
import { CsvViewer } from "./CsvViewer";
import { MarkdownViewer } from "./MarkdownViewer";

export function ArtifactViewer({ path, kind }: { path: string; kind: "csv" | "md" }) {
  if (kind === "csv") return <CsvViewer path={path} />;
  if (kind === "md") return <MarkdownViewer path={path} />;
  return <p className="text-xs text-slate-400">Unsupported artifact kind: {kind}</p>;
}
