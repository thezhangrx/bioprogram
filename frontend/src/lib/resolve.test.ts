import { describe, expect, it } from "vitest";
import { resolveRel } from "../components/artifacts/MarkdownViewer";

describe("artifact relative resolution", () => {
  it("resolves ../figures and plain sibling paths", () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    expect(resolveRel("/ws/projects/p1/analysis/summary/00_overview.md", "../figures/a.png"))
      .toBe("/ws/projects/p1/analysis/figures/a.png");
    expect(resolveRel("/ws/summary/x.md", "tables/e.csv"))
      .toBe("/ws/summary/tables/e.csv");
  });
});
