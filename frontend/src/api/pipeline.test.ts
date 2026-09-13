import { afterEach, describe, expect, it, vi } from "vitest";
import { pipelineApi } from "./pipeline";
import { filesApi } from "./files";

const ok = (body: unknown) => Promise.resolve({
  ok: true, status: 200, statusText: "OK", json: () => Promise.resolve(body),
} as Response);

describe("pipeline/files api clients", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("requests steps with an absolute output dir", async () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) => ok({ steps: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await pipelineApi.steps("/abs/out");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/pipeline/steps?output_dir=%2Fabs%2Fout");
    await pipelineApi.steps();
    expect(fetchMock.mock.calls[1][0]).toBe("/api/pipeline/steps");
  });

  it("posts step_id and options when running a step", async () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) =>
      ok({ status: "running", kind: "pipeline_train_grid" }));
    vi.stubGlobal("fetch", fetchMock);
    await pipelineApi.run("train_grid", { dry_run: true, output_dir: "/abs/out", options: { epochs: 3 } });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/pipeline/run");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      step_id: "train_grid", dry_run: true, output_dir: "/abs/out", options: { epochs: 3 },
    });
  });

  it("encodes file paths and exposes a raw url", async () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) => ok({ entries: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await filesApi.list("results/batch 1/summary");
    expect(fetchMock.mock.calls[0][0]).toContain("path=results%2Fbatch%201%2Fsummary");
    expect(filesApi.rawUrl("a/b c.csv")).toBe("/api/file-raw?path=a%2Fb%20c.csv");
  });
});
