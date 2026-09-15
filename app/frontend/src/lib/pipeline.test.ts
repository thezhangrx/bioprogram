import { describe, expect, it } from "vitest";
import type { PipelineStep } from "../api/pipeline";
import { canRun, confirmText, groupByCategory, statusTone, artifactLabel } from "./pipeline";

const step = (over: Partial<PipelineStep> = {}): PipelineStep => ({
  schema: "pipeline.step/1", step_id: "train_grid", title: "训练", category: "train",
  heavy: true, requires: [], description: "", kind: "subprocess", artifacts: [],
  command: "", status: "pending", ready: false, ...over,
});

describe("pipeline helpers", () => {
  it("groups steps by category in canonical order", () => {
    const groups = groupByCategory([
      step({ step_id: "a", category: "analysis" }),
      step({ step_id: "b", category: "data" }),
      step({ step_id: "c", category: "deliverable" }),
    ]);
    expect(groups.map((g) => g.category)).toEqual(["data", "analysis", "deliverable"]);
  });

  it("only allows running ready subprocess steps", () => {
    expect(canRun(step({ ready: true }))).toBe(true);
    expect(canRun(step({ ready: false }))).toBe(false);
    expect(canRun(step({ ready: true, kind: "internal" }))).toBe(false);
  });

  it("warns about heavy steps writing models/results/logs", () => {
    expect(confirmText(step({ heavy: true }))).toContain("models/");
    expect(confirmText(step({ heavy: false }))).not.toContain("models/");
    expect(confirmText(step({ kind: "internal", heavy: false }))).toContain("交付物核对");
  });

  it("maps status to tones and labels artifacts", () => {
    expect(statusTone("completed")).toBe("ok");
    expect(statusTone("running")).toBe("run");
    expect(statusTone("partial")).toBe("warn");
    expect(statusTone("pending")).toBe("idle");
    expect(artifactLabel({ rel: "summary/a.csv", exists: true })).toContain("✓");
    expect(artifactLabel({ rel: "summary/a.csv", exists: false })).toContain("✗");
  });
});
