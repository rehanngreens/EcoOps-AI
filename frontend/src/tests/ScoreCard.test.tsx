import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ScoreCard, ScoreComparison } from "../components/ScoreCard";
import { optimizeRecommended } from "./fixtures";

describe("ScoreCard", () => {
  it("renders composite score, grade, and all five components", () => {
    render(<ScoreCard score={optimizeRecommended.scores.baseline} />);
    expect(screen.getByTestId("score-value")).toHaveTextContent("0.20");
    expect(screen.getByTestId("score-grade")).toHaveTextContent("F");
    for (const name of [
      "resource_efficiency",
      "energy_efficiency",
      "carbon_impact",
      "cost_efficiency",
      "constraint_compliance",
    ]) {
      expect(screen.getByTestId(`bar-${name}`)).toBeInTheDocument();
    }
  });

  it("discloses methodology and disclaimer", () => {
    render(<ScoreCard score={optimizeRecommended.scores.baseline} />);
    expect(screen.getByText(/Weighted mean of five normalized components/i)).toBeInTheDocument();
    expect(screen.getByText(/Prototype heuristic score/i)).toBeInTheDocument();
  });
});

describe("ScoreComparison", () => {
  it("shows baseline, optimized, and improvement", () => {
    render(<ScoreComparison baseline={0.2} optimized={0.38} improvement={0.18} />);
    expect(screen.getByTestId("baseline-score")).toHaveTextContent("0.20");
    expect(screen.getByTestId("optimized-score")).toHaveTextContent("0.38");
    expect(screen.getByText("+0.18")).toBeInTheDocument();
  });
});
