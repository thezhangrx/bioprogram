import { afterEach, describe, expect, it, vi } from "vitest";
import { datasetApi } from "./dataset";

const ok = (body: unknown) => Promise.resolve({
  ok: true, status: 200, statusText: "OK", json: () => Promise.resolve(body),
} as Response);

describe("dataset api client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts the measured dataset paths for inspection", async () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) => ok({ cell_lines: [] }));
    vi.stubGlobal("fetch", fetchMock);
    await datasetApi.inspect(["data/source_data"]);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/dataset/inspect");
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({ paths: ["data/source_data"] });
  });

  it("sends decisions when writing the user mapping config", async () => {
    const fetchMock = vi.fn((_url: string, _init?: RequestInit) => ok({ config_path: "x" }));
    vi.stubGlobal("fetch", fetchMock);
    await datasetApi.mappingConfig({
      inspection: { mapping_items: [] } as never,
      decisions: { "CTCF:N": 1 },
      project_id: "proj_1",
    });
    const [, init] = fetchMock.mock.calls[0];
    const body = JSON.parse(String(init?.body));
    expect(body.decisions).toEqual({ "CTCF:N": 1 });
    expect(body.project_id).toBe("proj_1");
  });
});
