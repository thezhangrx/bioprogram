import { useEffect, useState } from "react";
import { qcApi } from "../api/qc";
import type { QcSession } from "../types";
import { ArtifactViewer } from "../components/artifacts/ArtifactViewer";
import { projectApi } from "../api/project";
import { QcDashboard } from "../components/QcDashboard";

export function StandaloneQcView(props: { onExit: () => void; onOpenProject: (id: string) => void }) {
  const [paths, setPaths] = useState("");
  const [sessions, setSessions] = useState<QcSession[]>([]);
  const [active, setActive] = useState<QcSession | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const reload = () => qcApi.list().then(setSessions).catch((e) => setErr(String(e)));
  useEffect(() => { void reload(); }, []); // eslint-disable-line

  const start = async () => {
    const list = paths.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!list.length) { setErr("请输入数据集路径"); return; }
    setBusy(true); setErr(null);
    try {
      const s = await qcApi.start(list, "standalone");
      const poll = async () => {
        const cur = await qcApi.get(s.session_id);
        if (cur.status === "running") { setTimeout(() => void poll(), 1200); } else { setActive(cur); void reload(); }
      };
      void poll();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold">数据质量体检</h1>
          <p className="text-sm text-slate-500">只读数据体检：不训练、不修改数据</p>
        </div>
        <button onClick={props.onExit} className="text-sm text-blue-600 hover:underline">← 首页</button>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <label className="text-xs font-medium text-slate-600">数据集路径（每行一个文件或目录）</label>
        <textarea
          value={paths}
          onChange={(e) => setPaths(e.target.value)}
          rows={3}
          className="mt-2 w-full rounded-lg border border-slate-200 p-2 font-mono text-xs outline-none focus:border-blue-400"
          placeholder={"/path/to/your.csv\n或包含多个 csv/tsv 的目录"}
        />
        <button
          onClick={() => void start()}
          disabled={busy}
          className="mt-2 rounded-md bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {busy ? "运行中…" : "运行 QC"}
        </button>
        {err && <p className="mt-2 text-xs text-red-600">{err}</p>}
      </div>

      {active && active.status === "completed" && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="mb-3 text-sm text-slate-600">
            Session <code className="rounded bg-slate-100 px-1">{active.session_id}</code> · {active.status}
          </p>
          <QcDashboard session={active} />
          <div className="mt-3 flex gap-2">
            <button onClick={() => {
              projectApi.fromQc(active.session_id, "Project from QC").then((m) => props.onOpenProject(m.project_id))
                .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
            }} className="rounded-md border border-blue-300 px-3 py-1 text-xs text-blue-700 hover:bg-blue-50">
              用该数据集创建项目（复用 QC 指纹；数据已变更会自动拒绝）
            </button>
          </div>
        </div>
      )}
      {active && active.status === "failed" && (
        <p className="rounded-lg border border-red-200 bg-red-50 p-3 text-xs text-red-700">
          QC 失败：{active.stderr_tail?.slice(-500) ?? "原因未知"}
        </p>
      )}

      <div>
        <h2 className="mb-2 text-sm font-semibold text-slate-700">历史记录</h2>
        <div className="space-y-1 text-xs">
          {sessions.map((s) => (
            <button key={s.session_id} onClick={() => setActive(s)} className="flex w-full items-center justify-between rounded-md border border-slate-200 bg-white px-3 py-2 hover:bg-slate-50">
              <span className="font-mono">{s.session_id}</span>
              <span className={s.status === "completed" ? "text-emerald-600" : s.status === "running" ? "text-blue-600" : "text-red-600"}>{s.status}</span>
            </button>
          ))}
          {sessions.length === 0 && <p className="text-slate-400">暂无 QC 会话</p>}
        </div>
      </div>
    </div>
  );
}
