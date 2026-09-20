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

  it("joins FastAPI list validation errors into one readable message", async () => {
    mockFetchOnce(422, {
      detail: [
        { loc: ["body", "workload"], msg: "peak_rps must be >= average_rps", type: "value_error" },
        { loc: ["body", "workload"], msg: "availability_target out of range", type: "value_error" },
      ],
    });
    await expect(analyzeManifest("junk", null)).rejects.toMatchObject({
      status: 422,
      message: "peak_rps must be >= average_rps; availability_target out of range",
    });
  });

  it("falls back to a generic message for non-JSON error bodies", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response("<html>Bad Gateway</html>", {
          status: 502,
          headers: { "Content-Type": "text/html" },
        }),
      ),
    );
    await expect(runOptimization("x")).rejects.toMatchObject({
      status: 502,
      message: "Request failed with status 502",
    });
  });
});
