import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RecommendationPanel } from "../components/RecommendationPanel";
import { optimizeNone, optimizeRecommended } from "./fixtures";

describe("RecommendationPanel", () => {
  it("shows items and savings for a recommendation", () => {
    render(<RecommendationPanel optimize={optimizeRecommended} loading={false} />);
    expect(screen.getByTestId("recommendation-status")).toHaveTextContent("Recommended");
    expect(screen.getByTestId("recommendation-items")).toHaveTextContent("8 cores");
    expect(screen.getByTestId("recommendation-items")).toHaveTextContent("2 cores");
    expect(screen.getByTestId("savings")).toHaveTextContent("$1401.60");
    expect(screen.getByTestId("optimized-score")).toHaveTextContent("0.38");
    expect(screen.getByTestId("rejected-list")).toHaveTextContent("cpu_headroom");
  });

  it("shows an explanatory state when nothing was accepted", () => {
    render(<RecommendationPanel optimize={optimizeNone} loading={false} />);
    expect(screen.getByTestId("no-recommendation")).toBeInTheDocument();
    expect(screen.queryByTestId("savings")).not.toBeInTheDocument();
    expect(screen.getByTestId("rejected-list")).toBeInTheDocument();
  });

  it("shows a spinner while optimizing", () => {
    render(<RecommendationPanel optimize={null} loading={true} />);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });

  it("prompts to run optimization before it has run", () => {
    render(<RecommendationPanel optimize={null} loading={false} />);
    expect(screen.getByText(/Run the optimization/i)).toBeInTheDocument();
  });
});
