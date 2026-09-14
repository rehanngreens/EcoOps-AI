import { render, screen, fireEvent } from "@testing-library/react";
import { vi, describe, it, expect } from "vitest";
import { UploadPanel } from "../components/UploadPanel";
import { DEMO_PRESETS } from "../services/apiClient";

describe("UploadPanel", () => {
  it("renders three demo presets", () => {
    render(<UploadPanel onAnalyze={vi.fn()} busy={false} />);
    expect(screen.getByTestId("preset-well")).toBeInTheDocument();
    expect(screen.getByTestId("preset-moderate")).toBeInTheDocument();
    expect(screen.getByTestId("preset-heavy")).toBeInTheDocument();
  });

  it("clicking a preset passes its YAML and canonical workload", () => {
    const onAnalyze = vi.fn();
    render(<UploadPanel onAnalyze={onAnalyze} busy={false} />);

    fireEvent.click(screen.getByTestId("preset-heavy"));

    expect(onAnalyze).toHaveBeenCalledTimes(1);
    const [yaml, workload] = onAnalyze.mock.calls[0];
    expect(yaml).toContain("kind: Deployment");
    expect(workload).toEqual({
      application_type: "e-commerce",
      expected_users: 10000,
      traffic_level: "medium",
      max_latency_ms: 150,
      availability_target: 99.9,
    });
  });

  it("preset YAML fixtures parse to the documented configs", () => {
    // The well preset must really be the small deployment, not the heavy one.
    const well = DEMO_PRESETS.find((preset) => preset.id === "well")!;
    expect(well.yaml).toContain("replicas: 2");
    const heavy = DEMO_PRESETS.find((preset) => preset.id === "heavy")!;
    expect(heavy.yaml).toContain("replicas: 8");
  });

  it("disables presets while busy", () => {
    render(<UploadPanel onAnalyze={vi.fn()} busy={true} />);
    expect(screen.getByTestId("preset-heavy")).toBeDisabled();
  });
});
