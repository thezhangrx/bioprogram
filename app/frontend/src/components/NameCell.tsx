import { useState } from "react";
import { DirPicker } from "./DirPicker";

/**
 * Cell 01 · Name
 * - 用户可**修改项目名**；前端不使用 batch 概念（batch 仅存在于命令行/调试参数）；
 * - 训练结果输出目标文件夹通过**弹窗选择**（绝对路径），不用手输；
 * - 该目录下的 results/、models/、logs/ 由后端按绝对路径派生并展示。
 */
export function NameCell({ name, outputDir, repoRoot, onRename, onPickOutput, projectId }:
  {
    name: string;
    outputDir: string;
    repoRoot?: string;
    projectId: string;
    onRename: (name: string) => Promise<void> | void;
    onPickOutput: (absPath: string) => Promise<void> | void;
  }) {
  const [draft, setDraft] = useState(name);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const results = outputDir ? `${outputDir.replace(/\/$/, "")}/results` : "—";
  const models = outputDir ? `${outputDir.replace(/\/$/, "")}/models` : "—";
  const logs = outputDir ? `${outputDir.replace(/\/$/, "")}/logs` : "—";

  return (
    <div className="space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="w-24 text-slate-500">项目名</span>
        <input value={draft} onChange={(e) => setDraft(e.target.value)}
               className="w-72 rounded-md border border-slate-200 px-2 py-1 outline-none focus:border-blue-400" />
        <button disabled={busy || !draft.trim() || draft === name}
                onClick={async () => { setBusy(true); try { await onRename(draft.trim()); } finally { setBusy(false); } }}
                className="rounded-md bg-blue-600 px-3 py-1 text-white hover:bg-blue-700 disabled:opacity-40">
          保存项目名
        </button>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className="w-24 text-slate-500">输出目录</span>
        <code className="rounded bg-slate-100 px-2 py-1 text-[11px]" data-testid="output-dir">
          {outputDir || "（尚未选择）"}
        </code>
        <button onClick={() => setOpen(true)}
                className="rounded-md border border-slate-300 px-3 py-1 hover:bg-slate-50">选择目录…</button>
      </div>

      <div className="rounded-lg border border-slate-100 bg-slate-50 p-2 text-[11px] text-slate-600">
        <p className="mb-1 font-semibold text-slate-500">该目录下的产物（后端按绝对路径派生）</p>
        <p>results : <code>{results}</code></p>
        <p>models&nbsp; : <code>{models}</code></p>
        <p>logs&nbsp;&nbsp;&nbsp; : <code>{logs}</code></p>
        {repoRoot && outputDir.startsWith(repoRoot) && !outputDir.startsWith(`${repoRoot}/workspace`) ? (
          <p className="mt-1 rounded bg-amber-50 p-1 text-amber-700">
            ⚠ 该目录位于仓库内（{repoRoot}）且不在 workspace/ 下：属于受保护的交付区，
            删除项目时**不会**删除它（请改选 workspace 下的目录以让输出可随项目清理）。
          </p>
        ) : (
          <p className="mt-1 text-slate-400">
            删除项目时会连同该输出目录一起清理；仓库自带的 results/ models/ logs/ 及任意下级目录受保护，不会被误删。
          </p>
        )}
      </div>

      <DirPicker open={open} initial={outputDir || undefined} title={`选择项目输出目录（${projectId}）`}
                 onClose={() => setOpen(false)}
                 onPick={async (p) => { setOpen(false); await onPickOutput(p); }} />
    </div>
  );
}
