import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { vi, describe, it, expect } from "vitest";
import { UploadPanel } from "../components/UploadPanel";
import { DEFAULT_WORKLOAD } from "../components/WorkloadForm";
import {
  DEMO_PRESETS,
  KUBERNETES_PRESETS,
  TERRAFORM_PRESETS,
} from "../services/apiClient";

function enterDemoBrowser() {
  fireEvent.click(screen.getByTestId("demo-enter"));
  return screen.getByTestId("demo-browser");
}

describe("UploadPanel demo section", () => {
  it("demo section is closed by default and opens into a format chooser", () => {
    render(<UploadPanel onAnalyze={vi.fn()} busy={false} />);
    expect(screen.queryByTestId("demo-browser")).not.toBeInTheDocument();

    enterDemoBrowser();
    expect(screen.getByTestId("demo-format-kubernetes")).toBeInTheDocument();
    expect(screen.getByTestId("demo-format-terraform")).toBeInTheDocument();
    // No scenarios until a format is chosen.
    expect(screen.queryByTestId("preset-heavy")).not.toBeInTheDocument();
  });

  it("choosing Kubernetes shows only Kubernetes scenarios and stages with the right filename", () => {
    const onAnalyze = vi.fn();
    render(<UploadPanel onAnalyze={onAnalyze} busy={false} />);
    enterDemoBrowser();
    fireEvent.click(screen.getByTestId("demo-format-kubernetes"));

    expect(screen.getByTestId("demo-scenarios-kubernetes")).toBeInTheDocument();
    expect(screen.getByTestId("preset-heavy")).toBeInTheDocument();
    expect(screen.queryByTestId("preset-tf-heavy")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("preset-heavy"));
    expect(screen.getByTestId("staged-file")).toHaveTextContent("heavy-deployment.yaml");
    expect(screen.getByTestId("workload-form")).toBeInTheDocument();
    expect(screen.getByDisplayValue("e-commerce")).toBeInTheDocument();
    expect(screen.getByDisplayValue("10000")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("analyze-button"));
    expect(onAnalyze).toHaveBeenCalledTimes(1);
    const [yaml, workload, fileName] = onAnalyze.mock.calls[0];
    expect(yaml).toContain("kind: Deployment");
    expect(workload.application_type).toBe("e-commerce");
    expect(fileName).toBe("heavy-deployment.yaml");
  });

  it("choosing Terraform shows only Terraform scenarios and stages .tf content", () => {
    const onAnalyze = vi.fn();
    render(<UploadPanel onAnalyze={onAnalyze} busy={false} />);
    enterDemoBrowser();
    fireEvent.click(screen.getByTestId("demo-format-terraform"));

    expect(screen.getByTestId("demo-scenarios-terraform")).toBeInTheDocument();
    expect(screen.getByTestId("preset-tf-heavy")).toBeInTheDocument();
    expect(screen.queryByTestId("preset-heavy")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("preset-tf-heavy"));
    expect(screen.getByTestId("staged-file")).toHaveTextContent("main-heavy-overprovisioned.tf");
    expect(screen.getByDisplayValue("e-commerce")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("analyze-button"));
    const [yaml, , fileName] = onAnalyze.mock.calls[0];
    expect(yaml).toContain('resource "aws_instance"');
    expect(fileName).toBe("main-heavy-overprovisioned.tf");
  });

  it("switching format swaps the scenario list; close collapses the whole section", () => {
    render(<UploadPanel onAnalyze={vi.fn()} busy={false} />);
    enterDemoBrowser();
    fireEvent.click(screen.getByTestId("demo-format-kubernetes"));
    expect(screen.getByTestId("preset-well")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("demo-format-terraform"));
    expect(screen.getByTestId("preset-tf-well")).toBeInTheDocument();
    expect(screen.queryByTestId("preset-well")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("demo-close"));
    expect(screen.queryByTestId("demo-browser")).not.toBeInTheDocument();
    expect(screen.getByTestId("demo-enter")).toBeEnabled();
  });

  it("staging a demo hides the demo section; reset restores the closed state", () => {
    render(<UploadPanel onAnalyze={vi.fn()} busy={false} />);
    enterDemoBrowser();
    fireEvent.click(screen.getByTestId("demo-format-terraform"));
    fireEvent.click(screen.getByTestId("preset-tf-well"));

    expect(screen.queryByTestId("demo-section")).not.toBeInTheDocument();
    expect(screen.getByTestId("workload-step")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("reset-button"));
    expect(screen.getByTestId("demo-section")).toBeInTheDocument();
    expect(screen.queryByTestId("demo-browser")).not.toBeInTheDocument();
    expect(screen.queryByTestId("workload-step")).not.toBeInTheDocument();
  });

  it("analyze sends the (possibly edited) workload with the file", () => {
    const onAnalyze = vi.fn();
    render(<UploadPanel onAnalyze={onAnalyze} busy={false} />);
    enterDemoBrowser();
    fireEvent.click(screen.getByTestId("demo-format-kubernetes"));
    fireEvent.click(screen.getByTestId("preset-heavy"));

    // The user edits the workload before analyzing.
    fireEvent.change(screen.getByLabelText("Expected users"), {
      target: { value: "25000" },
    });
    fireEvent.click(screen.getByTestId("analyze-button"));

    expect(onAnalyze).toHaveBeenCalledTimes(1);
    const [, workload] = onAnalyze.mock.calls[0];
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
    const [, workload, fileName] = onAnalyze.mock.calls[0];
    expect(workload).toMatchObject({ application_type: "database", expected_users: 50000 });
    expect(fileName).toBe("mine.yaml");
  });

  it("preset YAML and Terraform fixtures parse to the documented configs", () => {
    const well = KUBERNETES_PRESETS.find((preset) => preset.id === "well")!;
    expect(well.yaml).toContain("replicas: 2");
    const heavy = KUBERNETES_PRESETS.find((preset) => preset.id === "heavy")!;
    expect(heavy.yaml).toContain("replicas: 8");

    const tfHeavy = TERRAFORM_PRESETS.find((preset) => preset.id === "tf-heavy")!;
    expect(tfHeavy.yaml).toContain('instance_type = "m5.2xlarge"');
    expect(tfHeavy.yaml).toContain("count         = 8");

    // Flat list exposes both families with unique ids.
    expect(DEMO_PRESETS).toHaveLength(6);
    expect(new Set(DEMO_PRESETS.map((p) => p.id)).size).toBe(6);
  });

  it("disables demo controls while busy", async () => {
    const onAnalyze = vi.fn();
    const view = render(<UploadPanel onAnalyze={onAnalyze} busy={false} />);

    expect(screen.getByTestId("demo-enter")).toBeEnabled();
    view.rerender(<UploadPanel onAnalyze={onAnalyze} busy={true} />);
    expect(screen.getByTestId("demo-enter")).toBeDisabled();
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
