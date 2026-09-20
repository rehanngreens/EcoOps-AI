import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import App from "../App";
import { analyzeManifest } from "../services/apiClient";
import { analyzeResponse } from "./fixtures";

vi.mock("../services/apiClient", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../services/apiClient")>();
  return {
    ...actual,
    analyzeManifest: vi.fn(),
  };
});

const mockedAnalyze = vi.mocked(analyzeManifest);

function landOnUpload() {
  render(<App />);
  fireEvent.click(screen.getByTestId("entry-analyze"));
}

describe("App two-entry navigation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("landing shows both operating modes", () => {
    render(<App />);
    expect(screen.getByTestId("entry-analyze")).toBeDefined();
    expect(screen.getByTestId("entry-generate")).toBeDefined();
    expect(screen.getByText(/Analyze existing infrastructure/i)).toBeDefined();
    expect(screen.getByText(/Create sustainable infrastructure/i)).toBeDefined();
  });

  it("back from the upload flow returns to the landing page", () => {
    landOnUpload();
    expect(screen.getByTestId("drop-zone")).toBeDefined();
    fireEvent.click(screen.getByText(/Back/i));
    expect(screen.getByTestId("landing")).toBeDefined();
  });

  it("a completed analysis swaps the upload flow for the dashboard", async () => {
    mockedAnalyze.mockResolvedValueOnce(analyzeResponse);
    landOnUpload();

    // Stage the demo heavy preset, then analyze (mode A demo path).
    fireEvent.click(screen.getByTestId("demo-enter"));
    fireEvent.click(screen.getByTestId("demo-format-kubernetes"));
    fireEvent.click(screen.getByTestId("preset-heavy"));
    fireEvent.click(screen.getByTestId("analyze-button"));

    await waitFor(() => {
      expect(screen.getByTestId("new-analysis")).toBeDefined();
    });
    expect(mockedAnalyze).toHaveBeenCalledTimes(1);
  });

  it("reset from the dashboard returns to the landing page", async () => {
    mockedAnalyze.mockResolvedValueOnce(analyzeResponse);
    landOnUpload();
    fireEvent.click(screen.getByTestId("demo-enter"));
    fireEvent.click(screen.getByTestId("demo-format-kubernetes"));
    fireEvent.click(screen.getByTestId("preset-heavy"));
    fireEvent.click(screen.getByTestId("analyze-button"));
    await waitFor(() => expect(screen.getByTestId("new-analysis")).toBeDefined());

    fireEvent.click(screen.getByTestId("new-analysis"));
    expect(screen.getByTestId("landing")).toBeDefined();
  });
});
