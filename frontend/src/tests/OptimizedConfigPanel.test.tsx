import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { OptimizedConfigPanel } from "../components/OptimizedConfigPanel";
import { optimizedConfig } from "./fixtures";

describe("OptimizedConfigPanel", () => {
  it("prompts generation before it exists", () => {
    render(
      <OptimizedConfigPanel
        config={null}
        loading={false}
        error={null}
        onGenerate={vi.fn()}
      />,
    );
    expect(screen.getByTestId("generate-config")).toBeInTheDocument();
  });

  it("renders diff lines with the changes list", () => {
    render(
      <OptimizedConfigPanel
        config={optimizedConfig}
        loading={false}
        error={null}
        onGenerate={vi.fn()}
      />,
    );
    const diff = screen.getByTestId("diff-view");
    expect(diff).toHaveTextContent(/-\s+replicas: 8/);
    expect(diff).toHaveTextContent(/\+\s+replicas: 4/);
    expect(screen.getByText(/replicas: 8 → 4/)).toBeInTheDocument();
  });

  it("downloads the optimized YAML", () => {
    const createObjectURL = vi.fn(() => "blob:x");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", Object.assign(globalThis.URL, { createObjectURL, revokeObjectURL }));
    const click = vi.fn();
    const originalCreateElement = document.createElement.bind(document);
    const createElementSpy = vi
      .spyOn(document, "createElement")
      .mockImplementation((tag: string) => {
        if (tag === "a") {
          return { click, set href(_v: string) {}, set download(_v: string) {} } as never;
        }
        return originalCreateElement(tag);
      });

    render(
      <OptimizedConfigPanel
        config={optimizedConfig}
        loading={false}
        error={null}
        onGenerate={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("download-config"));

    expect(click).toHaveBeenCalled();
    expect(createObjectURL).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalled();

    createElementSpy.mockRestore();
    vi.unstubAllGlobals();
  });

  it("shows the friendly unavailable message instead of an error", () => {
    render(
      <OptimizedConfigPanel
        config={null}
        loading={false}
        error="Recommendations not found; run optimize first"
        onGenerate={vi.fn()}
      />,
    );
    expect(screen.getByTestId("config-unavailable")).toHaveTextContent(/run optimize first/i);
  });
});
