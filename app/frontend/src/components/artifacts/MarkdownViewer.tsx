// 科研化 Markdown 渲染 (安全): 先转义 HTML; 仅识别 md 结构; 图/artifact 链接经 Artifact Resolver。
import { createElement, useEffect, useState, type ReactNode } from "react";
import { artifactApi } from "../../api/artifacts";

function esc(s: string): string {
  return s
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

export function resolveRel(basePath: string, rel: string): string {
  const baseDir = basePath.includes("/") ? basePath.slice(0, basePath.lastIndexOf("/")) : "";
  const parts: string[] = baseDir.split("/").filter(Boolean);
  for (const seg of rel.split("/")) {
    if (seg === "..") parts.pop();
    else if (seg !== "." && seg !== "") parts.push(seg);
  }
  return (baseDir.startsWith("/") ? "/" : "") + parts.join("/");
}

interface Ctx { base: string; raw: (p: string) => string }

function tokenize(s: string): string[] {
  return s.split(/(%%IMG\|[^%]+%%|%%LINK\|[^%]+%%|\*\*[^*]+\*\*|`[^`]+`)/g);
}

function renderInline(rawText: string, ctx: Ctx): ReactNode[] {
  // 先抽取 IMG/LINK 的绝对候选; 其余按需转义 (HTML 始终被转义, 无注入)
  const pre = rawText
    .replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (_, alt: string, url: string) => `%%IMG|${alt}|${ctx.raw(resolveRel(ctx.base, url))}%%`)
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label: string, url: string) => `%%LINK|${label}|${ctx.raw(resolveRel(ctx.base, url))}%%`);
  return tokenize(esc(pre)).map((p, i) => {
    if (p.startsWith("%%IMG|")) {
      const m = p.slice(6, -2).split("|");
      const src = m.slice(1).join("|");
      return <img key={i} src={src} alt={m[0] || "figure"} loading="lazy"
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
                  className="my-2 max-w-full rounded-lg border border-slate-200" />;
    }
    if (p.startsWith("%%LINK|")) {
      const m = p.slice(7, -2).split("|");
      const href = m.slice(1).join("|");
      return <a key={i} href={href} target="_blank" rel="noreferrer"
                className="text-blue-600 underline decoration-blue-300 hover:text-blue-700">{m[0]}</a>;
    }
    if (/^\*\*.*\*\*$/.test(p)) return <strong key={i}>{p.slice(2, -2)}</strong>;
    if (/^`.*`$/.test(p)) return <code key={i} className="rounded bg-slate-100 px-1">{p.slice(1, -1)}</code>;
    return <span key={i}>{p}</span>;
  });
}

function renderMd(md: string, ctx: Ctx): ReactNode[] {
  const out: ReactNode[] = [];
  const lines = md.split(/\r?\n/);
  let i = 0, key = 0;
  while (i < lines.length) {
    const line = lines[i];
    const trim = line.trim();
    if (!trim) { i += 1; continue; }
    if (/^#{1,6}\s/.test(trim)) {
      const level = Math.min(6, line.match(/^#+/)![0].length);
      const text = trim.replace(/^#{1,6}\s*/, "");
      const cls = ["text-xl", "text-lg", "text-base", "text-sm", "text-sm", "text-sm"][level - 1];
      out.push(createElement("h" + level, { key: key++, className: `font-semibold text-slate-800 ${cls} mt-3 mb-1` }, renderInline(text, ctx)));
      i += 1; continue;
    }
    if (/^\s*[-*]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(<li key={key++}>{renderInline(lines[i].replace(/^\s*[-*]\s+/, ""), ctx)}</li>);
        i += 1;
      }
      out.push(<ul key={key++} className="list-disc pl-5 text-sm my-1">{items}</ul>);
      continue;
    }
    if (/^\s*>\s?/.test(line)) {
      const quote: string[] = [];
      while (i < lines.length && /^\s*>\s?/.test(lines[i])) { quote.push(lines[i].replace(/^\s*>\s?/, "")); i += 1; }
      out.push(<blockquote key={key++} className="border-l-2 border-slate-300 pl-3 text-slate-600 text-sm my-2">{renderInline(quote.join(" "), ctx)}</blockquote>);
      continue;
    }
    if (trim === "---" || trim === "***") { out.push(<hr key={key++} className="my-2 border-slate-200" />); i += 1; continue; }
    if (/^\s*```/.test(line)) {
      i += 1;
      const code: string[] = [];
      while (i < lines.length && !/^\s*```/.test(lines[i])) { code.push(lines[i]); i += 1; }
      i += 1;
      out.push(<pre key={key++} className="overflow-x-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100 my-2"><code>{code.join("\n")}</code></pre>);
      continue;
    }
    // 表格
    if (line.includes("|") && i + 1 < lines.length && /^\s*\|?[\s:|-]+\|?\s*$/.test(lines[i + 1])) {
      const head = line.split("|").slice(1, -1).map((s) => s.trim());
      i += 2;
      const body: string[][] = [];
      while (i < lines.length && lines[i].includes("|")) {
        body.push(lines[i].split("|").slice(1, -1).map((s) => s.trim()));
        i += 1;
      }
      out.push(
        <div key={key++} className="overflow-x-auto my-2">
          <table className="min-w-full text-xs border-collapse">
            <thead><tr>{head.map((h, k) => <th key={k} className="border-b-2 border-slate-200 bg-slate-50 px-2 py-1 text-left font-semibold">{renderInline(h, ctx)}</th>)}</tr></thead>
            <tbody>{body.map((row, r) => <tr key={r}>{row.map((c, k) => <td key={k} className="border-b border-slate-100 px-2 py-1">{renderInline(c, ctx)}</td>)}</tr>)}</tbody>
          </table>
        </div>,
      );
      continue;
    }
    // 段落
    const para: string[] = [line];
    i += 1;
    while (i < lines.length && lines[i].trim() !== "" && !/^#{1,6}\s/.test(lines[i]) && !/^\s*[-*]\s+/.test(lines[i])) {
      para.push(lines[i]); i += 1;
    }
    out.push(<p key={key++} className="text-sm text-slate-700 my-1.5 leading-relaxed">{renderInline(para.join(" "), ctx)}</p>);
  }
  return out;
}

export function MarkdownViewer({ path }: { path: string }) {
  const [state, setState] = useState<{ text: string; err?: string } | null>(null);
  useEffect(() => {
    let alive = true;
    artifactApi
      .asMarkdown(path)
      .then((r) => alive && setState({ text: r.text }))
      .catch((e) => alive && setState({ text: "", err: e instanceof Error ? e.message : String(e) }));
    return () => { alive = false; };
  }, [path]);
  if (!state) return <p className="text-xs text-slate-400">正在加载产物…</p>;
  if (state.err) return (
    <p className="text-sm text-amber-700">
      无法渲染该产物：{state.err}
      <span className="ml-1 text-slate-500">（该分析任务本次未执行或产物不存在；可在 Cell 06 勾选对应步骤后重跑）</span>
    </p>
  );
  const ctx: Ctx = { base: path, raw: artifactApi.rawUrl };
  return <div className="max-w-none">{renderMd(state.text, ctx)}</div>;
}
