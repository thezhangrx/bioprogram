import { act } from "react";
import { createRoot, type Root } from "react-dom/client";

export function renderJsx(node: React.ReactNode): { root: Root; host: HTMLElement } {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  act(() => root.render(node));
  return { root, host };
}

export function cleanupJsx(host: HTMLElement, root: Root) {
  act(() => root.unmount());
  host.remove();
}
