import { useEffect, useMemo, useState } from "react";
import { artifactApi } from "../../api/artifacts";
import { effectGlyph, formatNumber, isMissing, missingLabel } from "../../lib/format";
import { evidenceBadge } from "../EvidenceBadge";

const PAGE = 50;
const EFFECT_COL_RE = /(delta|d_r2|coefficient|effect|main_r2)/i;
const NO_DIRECTION_RE = /(gain|weight|cover|attention|pfi)/i;

type SortState = { col: number; asc: boolean } | null;

function renderValue(raw: string, hint: string, header: string) {
  if (isMissing(raw)) return missingLabel();
  if (/evidence|tier|strength/i.test(header) && hint !== "numeric") {
    return <span title={raw}>{evidenceBadge(raw)}</span>;
  }
  if (hint === "numeric") {
    const n = Number(raw);
    if (!Number.isFinite(n)) return <span title={raw}>{raw}</span>;
    if (!NO_DIRECTION_RE.test(header) && EFFECT_COL_RE.test(header)) {
      const g = effectGlyph(raw);
      if (g) return <span className={`inline-flex items-center gap-1 ${g.cls}`} title={raw}>{formatNumber(raw)} {g.arrow}</span>;
    }
    return <span title={raw}>{formatNumber(raw)}</span>;
  }
  return <span title={raw}>{raw}</span>;
}

export function CsvViewer({ path, title }: { path: string; title?: string }) {
  const [err, setErr] = useState<string | null>(null);
  const [cols, setCols] = useState<string[]>([]);
  const [rows, setRows] = useState<string[][]>([]);
  const [hints, setHints] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [truncated, setTruncated] = useState(false);
  const [page, setPage] = useState(0);
  const [q, setQ] = useState("");
  const [sort, setSort] = useState<SortState>(null);
  const [hidden, setHidden] = useState<Set<number>>(new Set());

  useEffect(() => {
    let alive = true;
    artifactApi.page(path, page * PAGE, PAGE)
      .then((r) => {
        if (!alive) return;
        if (r.kind !== "csv" || !r.columns || !r.rows) { setErr(`not a csv: ${r.name} (${r.kind})`); return; }
        setCols(r.columns); setRows(r.rows); setHints(r.type_hints ?? []);
        setTotal(r.data_rows ?? 0); setTruncated(!!r.truncated); setQ("");
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
    return () => { alive = false; };
  }, [path, page]);

  const pages = Math.max(1, Math.ceil(total / PAGE));

  const visibleCols = cols.map((c, i) => ({ c, i })).filter((x) => !hidden.has(x.i));

  const filtered = useMemo(() => {
    const tq = q.trim().toLowerCase();
    if (!tq) return rows;
    return rows.filter((r) => r.some((cell) => cell.toLowerCase().includes(tq)));
  }, [rows, q]);

  const sorted = useMemo(() => {
    if (!sort) return filtered;
    const si = sort.col;
    return [...filtered].sort((a, b) => {
      const hint = hints[si] ?? "text";
      if (hint === "numeric") {
        const na = Number(a[si]); const nb = Number(b[si]);
        const va = Number.isFinite(na) ? na : Number.NEGATIVE_INFINITY;
        const vb = Number.isFinite(nb) ? nb : Number.NEGATIVE_INFINITY;
        return sort.asc ? va - vb : vb - va;
      }
      return sort.asc
        ? String(a[si] ?? "").localeCompare(String(b[si] ?? ""))
        : String(b[si] ?? "").localeCompare(String(a[si] ?? ""));
    });
  }, [filtered, sort, hints]);

  const clickHeader = (ci: number) => setSort((s) =>
    s && s.col === ci ? { col: ci, asc: !s.asc } : { col: ci, asc: true });

  const toggleHidden = (ci: number) => setHidden((h) => {
    const n = new Set(h);
    if (n.has(ci)) n.delete(ci); else n.add(ci);
    return n;
  });

  if (err) return (
    <p className="text-sm text-amber-700">
      无法渲染该产物：{err}
      <span className="ml-1 text-slate-500">（该分析任务本次未执行或产物不存在）</span>
    </p>
  );

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="🔍 搜索（当前页）…"
               className="w-44 rounded-md border border-slate-200 px-2 py-1 outline-none focus:border-blue-400" />
        <span className="text-slate-400">{total.toLocaleString()} rows · 服务端分页</span>
        <details className="relative">
          <summary className="cursor-pointer rounded-md border border-slate-200 px-2 py-1 hover:bg-slate-50">列选择</summary>
          <div className="absolute z-20 mt-1 max-h-52 w-48 overflow-auto rounded-md border border-slate-200 bg-white p-2 shadow">
            {cols.map((c, i) => (
              <label key={i} className="flex items-center gap-1.5 py-0.5">
                <input type="checkbox" checked={!hidden.has(i)} onChange={() => toggleHidden(i)} /> {c}
              </label>
            ))}
          </div>
        </details>
        <div className="ml-auto flex items-center gap-1">
          <button disabled={page === 0} onClick={() => setPage(page - 1)} className="rounded px-2 py-0.5 hover:bg-slate-100 disabled:opacity-40">‹</button>
          <span>{page + 1}/{pages}</span>
          <button disabled={!truncated && page >= pages - 1} onClick={() => setPage(page + 1)} className="rounded px-2 py-0.5 hover:bg-slate-100 disabled:opacity-40">›</button>
        </div>
      </div>
      <div className="overflow-auto rounded-lg border border-slate-200" style={{ maxHeight: 430 }}>
        <table className="min-w-full border-collapse text-xs">
          <thead>
            <tr>
              {visibleCols.map(({ c, i }) => (
                <th key={i} onClick={() => clickHeader(i)}
                    className={`cursor-pointer select-none border-b border-slate-200 bg-slate-50 px-2 py-1.5 text-left font-semibold text-slate-600 ${i === visibleCols[0]?.i ? "sticky left-0 z-10 bg-slate-50" : ""}`}>
                  {c}{sort?.col === i ? (sort.asc ? " ▲" : " ▼") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, ri) => (
              <tr key={ri} className="hover:bg-slate-50">
                {visibleCols.map(({ c, i }) => (
                  <td key={i}
                      className={`border-b border-slate-100 px-2 py-1 whitespace-nowrap ${i === visibleCols[0]?.i ? "sticky left-0 bg-white font-medium" : ""}`}>
                    {renderValue(row[i] ?? "", hints[i] ?? "text", c)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {title && <p className="text-[11px] text-slate-400">Source artifact: {path}</p>}
    </div>
  );
}
