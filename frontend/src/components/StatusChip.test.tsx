// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { StatusChip } from "./StatusChip";
import { renderJsx, cleanupJsx } from "../test/render";

describe("StatusChip", () => {
  it("renders semantic status labels", () => {
    const a = renderJsx(<StatusChip status="completed" />);
    expect(a.host.textContent).toContain("Completed");
    cleanupJsx(a.host, a.root);
    const b = renderJsx(<StatusChip status="running" />);
    expect(b.host.textContent).toContain("Running");
    cleanupJsx(b.host, b.root);
    const c = renderJsx(<StatusChip status="unavailable" />);
    expect(c.host.textContent).toContain("Unavailable");
    cleanupJsx(c.host, c.root);
  });
});
