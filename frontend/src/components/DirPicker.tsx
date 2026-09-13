import { useEffect, useState } from "react";
import { fsApi, type FsListing } from "../api/fs";

/**
 * 目录选择弹窗：浏览绝对路径目录、可新建文件夹，选中后把**绝对路径**回传。
 * Web 端不做任何路径拼接，路径全部来自后端返回。
 */
export function DirPicker({ open, initial, title = "选择目录", onPick, onClose }:
  {
    open: boolean;
    initial?: string;
    title?: string;
    onPick: (absPath: string) => void;
    onClose: () => void;
  }) {
  const [listing, setListing] = useState<FsListing | null>(null);
  const [cur, setCur] = useState<string | undefined>(initial);
  const [newName, setNewName] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    fsApi.list(cur).then((l) => { setListing(l); setCur(l.path); setErr(null); })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, [open, cur]);

  if (!open) return null;

  const mkdir = async () => {
    if (!listing || !newName.trim()) return;
    try {
      const r = await fsApi.mkdir(listing.path, newName.trim());
      setNewName(""); setCur(r.path);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
         role="dialog" aria-modal="true">
      <div className="flex max-h-[80vh] w-[720px] flex-col rounded-xl bg-white shadow-xl">
        <header className="flex items-center gap-2 border-b border-slate-100 px-4 py-2.5">
          <h3 className="text-sm font-semibold">{title}</h3>
          <button onClick={onClose} className="ml-auto text-xs text-slate-500 hover:underline">关闭</button>
        </header>

        <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-2 text-[11px]">
          {(listing?.roots ?? []).map((r) => (
            <button key={r.path} onClick={() => setCur(r.path)}
                    className="rounded border border-slate-200 px-1.5 py-0.5 hover:bg-slate-50">{r.label}</button>
          ))}
          <span className="font-mono text-slate-500">{listing?.path}</span>
          {listing?.parent && (
            <button onClick={() => setCur(listing.parent as string)}
                    className="rounded border border-slate-200 px-1.5 py-0.5 hover:bg-slate-50">↑ 上一级</button>
          )}
        </div>

        <ul className="flex-1 overflow-auto px-2 py-1" data-testid="dir-list">
          {(listing?.entries ?? []).map((e) => (
            <li key={e.path}>
              <button onClick={() => setCur(e.path)}
                      className="flex w-full items-center gap-2 rounded px-2 py-1 text-left text-[12px] hover:bg-slate-50">
                <span>📁</span><span className="flex-1 truncate">{e.name}</span>
                {e.is_empty && <span className="text-[10px] text-slate-300">空</span>}
              </button>
            </li>
          ))}
          {listing && listing.entries.length === 0 && (
            <li className="px-2 py-1 text-[11px] text-slate-400">（没有子目录）</li>
          )}
        </ul>

        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 px-4 py-2 text-[11px]">
          <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="新建文件夹名"
                 className="w-40 rounded border border-slate-200 px-2 py-1" />
          <button onClick={() => void mkdir()} className="rounded border border-slate-300 px-2 py-1 hover:bg-slate-50">
            新建
          </button>
          <span className="flex-1" />
          {err && <span className="text-red-600">{err}</span>}
          <button onClick={() => listing && onPick(listing.path)}
                  className="rounded-md bg-blue-600 px-3 py-1 text-white hover:bg-blue-700">
            选择此目录
          </button>
        </div>
      </div>
    </div>
  );
}
