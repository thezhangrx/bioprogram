import { useCallback, useEffect, useState } from "react";
import { filesApi, type FileListing, type FilePreview } from "../api/files";

/** 项目文件浏览/查看：目录列表 + 文本/CSV/JSON/Markdown/图片预览（只读）。 */
export function FileBrowser({ path, onPathChange }:
  { path?: string; onPathChange?: (p: string) => void }) {
  const [cur, setCur] = useState(path ?? "results");
  const [listing, setListing] = useState<FileListing | null>(null);
  const [preview, setPreview] = useState<FilePreview | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => { if (path) setCur(path); }, [path]);

  const open = useCallback((p: string) => {
    setErr(null);
    filesApi.list(p).then((l) => { setListing(l); setPreview(null); setCur(l.path); onPathChange?.(l.path); })
      .catch(async () => {
        try {
          const pv = await filesApi.preview(p);
          setPreview(pv);
        } catch (e) { setErr(String(e)); }
      });
  }, [onPathChange]);

  useEffect(() => { open(cur); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <span className="font-mono">{listing?.path ?? cur}</span>
        {listing?.parent != null && (
          <button onClick={() => open(listing.parent as string)}
                  className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-50">↑ 上一级</button>
        )}
        <button onClick={() => open("results")}
                className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-50">results/</button>
        <button onClick={() => open(".")}
                className="rounded border border-slate-300 px-2 py-0.5 hover:bg-slate-50">项目根</button>
      </div>

      {err && <p className="text-[11px] text-red-600">{err}</p>}

      {listing && (
        <ul className="max-h-64 overflow-auto rounded border border-slate-200" data-testid="file-list">
          {listing.entries.map((e) => (
            <li key={e.path}>
              <button onClick={() => open(e.path)}
                      className="flex w-full items-center gap-2 px-2 py-1 text-left text-[11px] hover:bg-slate-50">
                <span>{e.is_dir ? "📁" : e.kind === "image" ? "🖼" : e.kind === "binary" ? "📦" : "📄"}</span>
                <span className="flex-1 truncate">{e.name}</span>
                <span className="text-slate-400">{e.is_dir ? "" : `${Math.max(1, Math.round(e.size / 1024))} KB`}</span>
              </button>
            </li>
          ))}
          {listing.entries.length === 0 && <li className="px-2 py-1 text-[11px] text-slate-400">（空目录）</li>}
        </ul>
      )}

      {preview && (
        <div className="rounded border border-slate-200 p-2" data-testid="file-preview">
          <div className="flex items-center gap-2 text-[11px]">
            <span className="font-mono">{preview.path}</span>
            <span className="text-slate-400">{preview.kind} · {Math.max(1, Math.round(preview.size / 1024))} KB</span>
            {preview.truncated && <span className="text-amber-600">（已截断）</span>}
            <a href={filesApi.rawUrl(preview.path)} target="_blank" rel="noreferrer"
               className="text-blue-600 underline">原始文件</a>
            <button onClick={() => setPreview(null)} className="text-slate-500 underline">关闭</button>
          </div>
          {preview.kind === "image" && (
            <img src={filesApi.rawUrl(preview.path)} alt={preview.name}
                 className="mt-2 max-h-72 rounded border border-slate-200" />
          )}
          {preview.columns && preview.rows && (
            <div className="mt-2 max-h-72 overflow-auto">
              <table className="w-full text-[10px]">
                <thead className="bg-slate-50">
                  <tr>{preview.columns.map((c, i) => <th key={i} className="border px-1 py-0.5 text-left">{c}</th>)}</tr>
                </thead>
                <tbody>
                  {preview.rows.slice(0, 50).map((r, i) => (
                    <tr key={i}>{r.map((c, j) => <td key={j} className="border px-1 py-0.5">{c}</td>)}</tr>
                  ))}
                </tbody>
              </table>
              <p className="mt-1 text-[10px] text-slate-400">共 {preview.data_rows} 行（预览前 50 行）</p>
            </div>
          )}
          {!preview.columns && preview.text && (
            <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-[10px]">{preview.text.slice(0, 20000)}</pre>
          )}
          {preview.note && <p className="mt-1 text-[11px] text-slate-500">{preview.note}</p>}
        </div>
      )}
    </div>
  );
}
