import { useState } from "react";
import { HomeView } from "./views/HomeView";
import { WorkspaceView } from "./views/WorkspaceView";
import { projectApi } from "./api/project";
import { StandaloneQcView } from "./views/StandaloneQcView";

type Screen =
  | { name: "home" }
  | { name: "project"; id: string }
  | { name: "qc" };

export default function App() {
  const [screen, setScreen] = useState<Screen>({ name: "home" });
  const [busy, setBusy] = useState(false);

  /** Create Project：直接创建并进入 Workspace（项目名与输出目录在 Cell 01 设置）。 */
  const createAndOpen = async () => {
    if (busy) return;
    setBusy(true);
    try {
      const m = await projectApi.create(`Project ${new Date().toISOString().slice(0, 16).replace("T", " ")}`, []);
      setScreen({ name: "project", id: m.project_id });
    } finally { setBusy(false); }
  };

  if (screen.name === "home") {
    return (
      <div className="h-screen">
        <HomeView onCreate={() => void createAndOpen()} creating={busy}
                  onQc={() => setScreen({ name: "qc" })}
                  onOpen={(id) => setScreen({ name: "project", id })} />
      </div>
    );
  }
  if (screen.name === "qc") {
    return (
      <div className="h-screen overflow-y-auto">
        <StandaloneQcView onExit={() => setScreen({ name: "home" })}
                          onOpenProject={(id) => setScreen({ name: "project", id })} />
      </div>
    );
  }
  return <WorkspaceView projectId={screen.id} onExit={() => setScreen({ name: "home" })} />;
}
