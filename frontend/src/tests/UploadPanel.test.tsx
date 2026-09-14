import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect } from "vitest";
import { UploadPanel } from "../components/UploadPanel";
import { DEFAULT_WORKLOAD } from "../components/WorkloadForm";
import { DEMO_PRESETS } from "../services/apiClient";

describe("UploadPanel", () => {
  it("presets stage a file and pre-fill the workload form", () => {
    render(<UploadPanel onAnalyze={vi.fn()} busy={false} />);
    fireEvent.click(screen.getByTestId("preset-heavy"));

    expect(screen.getByTestId("staged-file")).toHaveTextContent("heavy-deployment.yaml");
    expect(screen.getByTestId("workload-form")).toBeInTheDocument();
    expect(screen.getByDisplayValue("e-commerce")).toBeInTheDocument();
    expect(screen.getByDisplayValue("10000")).toBeInTheDocument();
  });

  it("preset YAML fixtures parse to the documented configs", () => {
    const well = DEMO_PRESETS.find((preset) => preset.id === "well")!;
    expect(well.yaml).toContain("replicas: 2");
    const heavy = DEMO_PRESETS.find((preset) => preset.id === "heavy")!;
    expect(heavy.yaml).toContain("replicas: 8");
  });

  it("analyze sends the (possibly edited) workload with the file", () => {
    const onAnalyze = vi.fn();
    render(<UploadPanel onAnalyze={onAnalyze} busy={false} />);
    fireEvent.click(screen.getByTestId("preset-heavy"));

    // The user edits the workload before analyzing.
    fireEvent.change(screen.getByLabelText("Expected users"), {
      target: { value: "25000" },
    });
    fireEvent.click(screen.getByTestId("analyze-button"));

    expect(onAnalyze).toHaveBeenCalledTimes(1);
    const [yaml, workload] = onAnalyze.mock.calls[0];
    expect(yaml).toContain("kind: Deployment");
    expect(workload.expected_users).toBe(25000);
    expect(workload.application_type).toBe("e-commerce");
  });

  it("custom upload starts from backend defaults, editable before analyze", async () => {
    const onAnalyze = vi.fn();
    render(<UploadPanel onAnalyze={onAnalyze} busy={false} />);
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, {
      target: { files: [new File(["kind: Deployment"], "mine.yaml")] },
    });

    // FileReader loads asynchronously.
    await waitFor(() => expect(screen.getByTestId("staged-file")).toHaveTextContent("mine.yaml"));
    // Backend defaults pre-filled.
    expect(screen.getByDisplayValue("rest-api")).toBeInTheDocument();
    expect(screen.getByDisplayValue("1000")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Application type"), {
      target: { value: "database" },
    });
    fireEvent.change(screen.getByLabelText("Expected users"), {
      target: { value: "50000" },
    });
    fireEvent.click(screen.getByTestId("analyze-button"));

    expect(onAnalyze).toHaveBeenCalledTimes(1);
    const [, workload] = onAnalyze.mock.calls[0];
    expect(workload).toMatchObject({ application_type: "database", expected_users: 50000 });
  });

  it("presets are hidden once a file is staged; reset brings them back", () => {
    render(<UploadPanel onAnalyze={vi.fn()} busy={false} />);
    fireEvent.click(screen.getByTestId("preset-well"));
    expect(screen.queryByTestId("preset-moderate")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("reset-button"));
    expect(screen.getByTestId("preset-moderate")).toBeInTheDocument();
    expect(screen.queryByTestId("workload-step")).not.toBeInTheDocument();
  });

  it("disables analyze and presets while busy", async () => {
    const onAnalyze = vi.fn();
    const view = render(<UploadPanel onAnalyze={onAnalyze} busy={false} />);

    // While idle, presets are enabled.
    expect(screen.getByTestId("preset-heavy")).toBeEnabled();
    fireEvent.click(screen.getByTestId("preset-heavy"));
    await waitFor(() => expect(screen.getByTestId("analyze-button")).toBeEnabled());

    // Re-render with busy=true (as UploadPage does during analysis).
    view.rerender(<UploadPanel onAnalyze={onAnalyze} busy={true} />);
    expect(screen.getByTestId("analyze-button")).toBeDisabled();
    expect(screen.getByTestId("reset-button")).toBeDisabled();
  });

  it("default workload matches the backend schema defaults", () => {
    expect(DEFAULT_WORKLOAD).toEqual({
      application_type: "rest-api",
      expected_users: 1000,
      traffic_level: "medium",
      max_latency_ms: 200,
      availability_target: 99.0,
    });
  });
});
