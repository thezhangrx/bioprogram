// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { evidenceBadge } from "./EvidenceBadge";
import { renderJsx, cleanupJsx } from "../test/render";

describe("EvidenceBadge (rendering only, no classification)", () => {
  it("maps known backend evidence strings to badges", () => {
    const a = renderJsx(<>{evidenceBadge("Strong convergent evidence")}</>);
    expect(a.host.textContent).toContain("Strong convergent evidence");
    cleanupJsx(a.host, a.root);
    const b = renderJsx(<>{evidenceBadge("Inconclusive")}</>);
    expect(b.host.textContent).toContain("Inconclusive");
    cleanupJsx(b.host, b.root);
  });
  it("passes through unknown values unchanged (no invention)", () => {
    const c = renderJsx(<>{evidenceBadge("Custom note")}</>);
    expect(c.host.textContent).toContain("Custom note");
    cleanupJsx(c.host, c.root);
  });
});
