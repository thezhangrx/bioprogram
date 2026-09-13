import { useState, type ReactNode } from "react";
import type { StageKey, StageStatus } from "../types";
import { StatusChip } from "./StatusChip";

export function NotebookCell(props: {
  index: number;
  title: string;
  status: StageStatus;
  hint?: string;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
      <header className="flex items-center gap-3 border-b border-slate-100 px-4 py-2.5">
        <span className="font-mono text-xs text-slate-400">Cell {String(props.index).padStart(2, "0")}</span>
        <h3 className="text-sm font-semibold text-slate-800">{props.title}</h3>
        {props.status !== "pending" && <StatusChip status={props.status} />}
        {props.hint && <span className="text-xs text-slate-400 truncate">{props.hint}</span>}
        <div className="ml-auto flex items-center gap-1 text-xs">
          {props.actions}
          <button
            className="rounded-md px-2 py-1 text-slate-500 hover:bg-slate-100"
            onClick={() => setCollapsed((c) => !c)}
          >
            {collapsed ? "Expand" : "Collapse"}
          </button>
        </div>
      </header>
      {!collapsed && <div className="px-4 py-3">{props.children ?? <p className="text-xs text-slate-400">—</p>}</div>}
    </section>
  );
}
