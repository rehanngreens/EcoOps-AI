import { describe, it, expect, vi, afterEach } from "vitest";
import { ApiError, analyzeManifest, runOptimization } from "../services/apiClient";

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("apiClient", () => {
  it("maps backend 400 detail messages", async () => {
    mockFetchOnce(400, { detail: "Unsupported file type '.txt'" });
    await expect(analyzeManifest("junk", null)).rejects.toMatchObject({
      status: 400,
      message: "Unsupported file type '.txt'",
    });
  });

  it("maps backend 404 for optimize-before-analyze", async () => {
    mockFetchOnce(404, { detail: "Analysis 'x' not found" });
    await expect(runOptimization("x")).rejects.toBeInstanceOf(ApiError);
  });

  it("maps backend 503 model-unavailable", async () => {
    mockFetchOnce(503, { detail: "Model artifacts are unavailable. Run: python ml/train_model.py" });
    await expect(runOptimization("x")).rejects.toMatchObject({
      status: 503,
      message: expect.stringContaining("train_model"),
    });
  });
});
