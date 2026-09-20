import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import { vi, describe, it, expect, beforeEach } from "vitest";
import { DashboardPage } from "../pages/DashboardPage";
import { analyzeResponse, optimizeRecommended } from "./fixtures";
import * as apiClient from "../services/apiClient";

vi.mock("../services/apiClient", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../services/apiClient")>()),
  fetchScore: vi.fn(),
  runOptimization: vi.fn(),
  fetchOptimizedConfig: vi.fn(),
}));

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.mocked(apiClient.fetchScore).mockResolvedValue({
      analysis_id: analyzeResponse.analysis_id,
      score: optimizeRecommended.scores.baseline,
    });
    vi.mocked(apiClient.runOptimization).mockResolvedValue(optimizeRecommended);
  });

  it("renders overview sections and computes the score", async () => {
    render(<DashboardPage analysis={analyzeResponse} onReset={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("score-value")).toBeInTheDocument();
    });
    expect(screen.getByTestId("est-cost")).toHaveTextContent("$2336.00");
    expect(screen.getByTestId("problem-list")).toHaveTextContent(/user capacity/i);
    expect(screen.getByText("Current configuration")).toBeInTheDocument();
  });

  it("runs optimization and shows the recommendation with improvement", async () => {
    render(<DashboardPage analysis={analyzeResponse} onReset={vi.fn()} />);

    fireEvent.click(screen.getByTestId("run-optimize"));

    await waitFor(() => {
      expect(screen.getByTestId("recommendation-status")).toHaveTextContent("Recommended");
    });
    expect(screen.getByTestId("optimized-score")).toBeInTheDocument();
    expect(apiClient.runOptimization).toHaveBeenCalledWith(analyzeResponse.analysis_id);
  });

  it("returns to upload on New analysis", () => {
    const onReset = vi.fn();
    render(<DashboardPage analysis={analyzeResponse} onReset={onReset} />);
    fireEvent.click(screen.getByTestId("new-analysis"));
    expect(onReset).toHaveBeenCalledTimes(1);
  });
});
