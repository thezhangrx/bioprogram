import { useEffect, useState } from "react";
import { projectApi } from "../api/project";
import type { ProjectManifest } from "../types";

export function HomeView(props: {
  onCreate: () => void;
  onQc: () => void;
  onOpen: (id: string) => void;
  creating?: boolean;
}) {
  const [projects, setProjects] = useState<ProjectManifest[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pending, setPending] = useState<ProjectManifest | null>(null);
  const plist = projects ?? [];

  const reload = () => projectApi.list().then(setProjects).catch(() => setProjects([]));
  useEffect(() => { void reload(); }, []);

  const doDelete = async (p: ProjectManifest) => {
    try {
      await projectApi.remove(p.project_id);
      setPending(null);
      setProjects((cur) => (cur ?? []).filter((x) => x.project_id !== p.project_id));
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  };

  return (
    <div className="mx-auto flex h-full max-w-4xl flex-col items-center justify-center gap-8 px-6 py-10">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">CRISPR Scientific Workspace</h1>
        <p className="mt-1 text-sm text-slate-500">从数据体检到证据整合的完整科研工作流</p>
      </div>

      <div className="grid w-full grid-cols-1 gap-4 sm:grid-cols-2">
        <button onClick={props.onCreate} disabled={props.creating}
                className="rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:border-blue-300 hover:shadow disabled:opacity-50">
          <p className="text-base font-semibold text-slate-800">
            {props.creating ? "Creating…" : "Create Project"}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            直接进入 Workspace（Cell 01 项目名 + 输出目录 → Cell 02 选数据集 → … → Cell 08 查看文件）
          </p>
        </button>
        <button onClick={props.onQc}
                className="rounded-xl border border-slate-200 bg-white p-5 text-left shadow-sm transition hover:border-blue-300 hover:shadow">
          <p className="text-base font-semibold text-slate-800">Dataset Quality Check</p>
          <p className="mt-1 text-sm text-slate-500">独立数据体检：只读检测结构与质量，无需进入训练</p>
        </button>
      </div>

      <div className="w-full">
        <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-400">Projects</p>
        {err && <p className="mb-2 text-sm text-red-600">{err}</p>}
        {projects === null && <p className="text-sm text-slate-400">Loading…</p>}
        {projects !== null && projects.length === 0 && <p className="text-sm text-slate-400">暂无项目 — 点击上方创建或从 QC 结果生成</p>}
        <ul className="space-y-1">
          {plist.map((p) => (
            <li key={p.project_id}
                className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 hover:border-blue-200">
              <button onClick={() => props.onOpen(p.project_id)} className="flex flex-1 items-center justify-between text-left">
                <span>
                  <span className="text-sm font-medium text-slate-800">{p.name}</span>
                  <span className="ml-2 font-mono text-[11px] text-slate-400">{p.project_id}</span>
                  {(p.config as { output_dir?: string } | undefined)?.output_dir && (
                    <span className="ml-2 rounded bg-slate-100 px-1 text-[10px] text-slate-500">
                      输出: {(p.config as { output_dir?: string }).output_dir}
                    </span>
                  )}
                </span>
                <StageSummary stages={p.stages} />
              </button>
              <button onClick={() => setPending(p)} title="删除项目（含训练结果）"
                      aria-label={`delete-${p.project_id}`}
                      className="rounded-md border border-red-200 px-2 py-0.5 text-[11px] text-red-600 hover:bg-red-50">
                删除
              </button>
            </li>
          ))}
        </ul>
      </div>

      {pending && (
        <DeleteDialog project={pending} onCancel={() => setPending(null)}
                      onConfirm={() => void doDelete(pending)} />
      )}
    </div>
  );
}

/** 删除确认弹窗：显示将删除的绝对路径，并强制倒计时后才可点击（防误删）。 */
function DeleteDialog({ project, onCancel, onConfirm }:
  { project: ProjectManifest; onCancel: () => void; onConfirm: () => void }) {
  const WAIT = 3;
  const [left, setLeft] = useState(WAIT);
  const [busy, setBusy] = useState(false);
  const output = (project.config as { output_dir?: string } | undefined)?.output_dir;

  useEffect(() => {
    if (left <= 0) return;
    const t = window.setTimeout(() => setLeft((v) => v - 1), 1000);
    return () => window.clearTimeout(t);
  }, [left]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4"
         role="dialog" aria-modal="true">
      <div className="w-[520px] rounded-xl bg-white p-5 shadow-xl">
        <h3 className="text-base font-semibold text-red-600">删除项目「{project.name}」</h3>
        <p className="mt-2 text-xs text-slate-600">将**永久删除**以下内容（不可恢复）：</p>
        <ul className="mt-2 space-y-1 rounded border border-slate-200 bg-slate-50 p-2 font-mono text-[11px]">
          <li>workspace/projects/{project.project_id}/</li>
          {output ? <li>{output}/　（含 results / models / logs 全部训练结果）</li>
            : <li className="text-slate-400">（该项目尚未选择输出目录）</li>}
        </ul>
        <p className="mt-2 text-[11px] text-slate-500">
          注意：仓库自带的 results/ models/ logs/ 属于交付物，受保护不会被删除。
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button onClick={onCancel} className="rounded-md border border-slate-300 px-3 py-1 text-sm hover:bg-slate-50">
            取消
          </button>
          <button disabled={left > 0 || busy}
                  onClick={async () => { setBusy(true); try { onConfirm(); } finally { setBusy(false); } }}
                  className="rounded-md bg-red-600 px-3 py-1 text-sm text-white hover:bg-red-700 disabled:opacity-40">
            {left > 0 ? `确认删除（${left}s）` : "确认删除"}
          </button>
        </div>
      </div>
    </div>
  );
}

function StageSummary({ stages }: { stages: Record<string, string> }) {
  const order = ["data", "qc", "mapping", "training", "analysis", "reports"];
  const color: Record<string, string> = {
    completed: "bg-emerald-500", running: "bg-blue-500", failed: "bg-red-500", pending: "bg-slate-200", warning: "bg-amber-400",
  };
  return (
    <span className="flex items-center gap-1">
      {order.map((s) => (
        <span key={s} title={`${s}: ${stages[s] ?? "pending"}`} className={`size-2 rounded-full ${color[stages[s] ?? "pending"] ?? "bg-slate-200"}`} />
      ))}
    </span>
  );
}
