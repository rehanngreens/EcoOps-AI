import { useRef, useState } from "react";
import type { WorkloadProfile } from "../types/api";
import {
  COMPOSE_PRESETS,
  KUBERNETES_PRESETS,
  TERRAFORM_PRESETS,
  type DemoPreset,
} from "../services/apiClient";
import { Card } from "./ui/primitives";
import { DEFAULT_WORKLOAD, WorkloadForm } from "./WorkloadForm";

type StagedFile = { name: string; yaml: string } | null;
type DemoFormat = "kubernetes" | "terraform" | "docker-compose";

const DEMO_FAMILIES: Array<{
  format: DemoFormat;
  title: string;
  blurb: string;
  presets: DemoPreset[];
}> = [
  {
    format: "kubernetes",
    title: "Kubernetes demos",
    blurb: "Deployment manifests — full pipeline incl. optimized YAML",
    presets: KUBERNETES_PRESETS,
  },
  {
    format: "terraform",
    title: "Terraform demos",
    blurb: "AWS EC2 configurations — full analysis; optimized generation is Kubernetes-only",
    presets: TERRAFORM_PRESETS,
  },
  {
    format: "docker-compose",
    title: "Docker Compose demos",
    blurb: "Multi-service stacks — full analysis; optimized generation is Kubernetes-only",
    presets: COMPOSE_PRESETS,
  },
];

export function UploadPanel({
  onAnalyze,
  busy,
}: {
  onAnalyze: (yaml: string, workload: WorkloadProfile, fileName?: string) => void;
  busy: boolean;
}) {
  const [staged, setStaged] = useState<StagedFile>(null);
  const [workload, setWorkload] = useState<WorkloadProfile>(DEFAULT_WORKLOAD);
  const [presetId, setPresetId] = useState<string | null>(null);
  const [stagedFileName, setStagedFileName] = useState<string | null>(null);
  const [demoOpen, setDemoOpen] = useState(false);
  const [demoFormat, setDemoFormat] = useState<DemoFormat | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const closeDemoSection = () => {
    setDemoOpen(false);
    setDemoFormat(null);
  };

  const stageFile = (
    name: string,
    yaml: string,
    preset: DemoPreset | null,
    fileNameForUpload?: string,
  ) => {
    setStaged({ name, yaml });
    setStagedFileName(fileNameForUpload ?? null);
    setPresetId(preset?.id ?? null);
    if (preset) {
      setWorkload(preset.workload);
    } else if (staged === null) {
      setWorkload(DEFAULT_WORKLOAD);
    }
  };

  const readFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      stageFile(file.name, String(reader.result), null, file.name);
      closeDemoSection();
    };
    reader.readAsText(file);
  };

  const runAnalysis = () => {
    if (!staged) return;
    onAnalyze(staged.yaml, workload, stagedFileName ?? staged.name);
  };

  const reset = () => {
    setStaged(null);
    setStagedFileName(null);
    setPresetId(null);
    setWorkload(DEFAULT_WORKLOAD);
    closeDemoSection();
  };

  return (
    <Card title="Analyze existing infrastructure (Kubernetes or Terraform)">
      {/* Step 1: the IaC file */}
      <div
        data-testid="drop-zone"
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          const file = event.dataTransfer.files[0];
          if (file) readFile(file);
        }}
        onClick={() => fileInput.current?.click()}
        className={`cursor-pointer rounded-lg border-2 border-dashed px-6 py-8 text-center transition-colors ${
          staged
            ? "border-eco-500 bg-eco-50"
            : dragOver
              ? "border-eco-500 bg-eco-50"
              : "border-slate-300 hover:border-eco-500 hover:bg-eco-50/50"
        }`}
      >
        {staged ? (
          <p className="text-sm font-medium text-eco-700" data-testid="staged-file">
            ✓ {staged.name} — choose the workload below, then analyze
          </p>
        ) : (
          <>
            <p className="text-sm font-medium text-slate-700">
              Drag &amp; drop a Kubernetes YAML, Terraform, or Compose file here
            </p>
            <p className="mt-1 text-xs text-slate-400">or click to browse (.yaml / .yml / .tf)</p>
          </>
        )}
        <input
          ref={fileInput}
          type="file"
          accept=".yaml,.yml,.tf"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) readFile(file);
          }}
        />
      </div>

      {/* Demo section: enter, choose a format, choose a scenario. */}
      {!staged && (
        <div className="mt-6" data-testid="demo-section">
          {!demoOpen ? (
            <button
              type="button"
              data-testid="demo-enter"
              disabled={busy}
              onClick={() => {
                setDemoOpen(true);
                setDemoFormat(null);
              }}
              className="rounded-lg border border-eco-200 bg-eco-50 px-4 py-2 text-sm font-medium text-eco-700 transition-colors hover:bg-eco-100 disabled:opacity-50"
            >
              Try a guided demo scenario →
            </button>
          ) : (
            <div
              data-testid="demo-browser"
              className="rounded-lg border border-slate-200 bg-slate-50/60 p-4"
            >
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                  Demo scenarios
                </p>
                <button
                  type="button"
                  data-testid="demo-close"
                  onClick={closeDemoSection}
                  className="text-xs font-medium text-slate-500 hover:text-slate-700"
                >
                  Close
                </button>
              </div>

              <p className="mt-2 text-sm font-medium text-slate-700">
                Which infrastructure type do you want to demo?
              </p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {DEMO_FAMILIES.map((family) => (
                  <button
                    key={family.format}
                    type="button"
                    data-testid={`demo-format-${family.format}`}
                    disabled={busy}
                    onClick={() => setDemoFormat(family.format)}
                    className={`rounded-lg border px-3 py-3 text-left transition-colors disabled:opacity-50 ${
                      demoFormat === family.format
                        ? "border-eco-500 bg-eco-50"
                        : "border-slate-200 bg-white hover:border-eco-500 hover:bg-eco-50"
                    }`}
                  >
                    <span className="block text-sm font-medium text-slate-800">
                      {family.title}
                    </span>
                    <span className="mt-0.5 block text-xs text-slate-400">{family.blurb}</span>
                  </button>
                ))}
              </div>

              {demoFormat && (
                <div className="mt-4" data-testid={`demo-scenarios-${demoFormat}`}>
                  <p className="text-sm font-medium text-slate-700">
                    Choose a scenario
                    <span className="ml-1 text-xs font-normal text-slate-400">
                      (stages the file and pre-fills the editable workload)
                    </span>
                  </p>
                  <div className="mt-2 grid gap-2 sm:grid-cols-3">
                    {DEMO_FAMILIES.find((f) => f.format === demoFormat)!.presets.map((preset) => (
                      <button
                        key={preset.id}
                        type="button"
                        data-testid={`preset-${preset.id}`}
                        disabled={busy}
                        onClick={() => {
                          stageFile(preset.fileName, preset.yaml, preset, preset.fileName);
                          closeDemoSection();
                        }}
                        className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-left transition-colors hover:border-eco-500 hover:bg-eco-50 disabled:opacity-50"
                      >
                        <span className="block text-sm font-medium text-slate-800">
                          {preset.label}
                        </span>
                        <span className="block text-xs text-slate-400">{preset.description}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Step 2: the workload profile (always visible once a file is staged). */}
      {staged && (
        <div className="mt-6" data-testid="workload-step">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
              Workload profile {presetId && <span className="normal-case">(from {presetId} preset — editable)</span>}
            </p>
            <button
              type="button"
              data-testid="change-file"
              onClick={() => fileInput.current?.click()}
              className="text-xs font-medium text-eco-700 hover:underline"
            >
              Change file
            </button>
          </div>
          <WorkloadForm workload={workload} onChange={setWorkload} />

          <div className="mt-5 flex items-center gap-3">
            <button
              type="button"
              onClick={runAnalysis}
              disabled={busy}
              data-testid="analyze-button"
              className="rounded-lg bg-eco-600 px-5 py-2 text-sm font-medium text-white transition-colors hover:bg-eco-700 disabled:opacity-50"
            >
              {busy ? "Analyzing…" : "Analyze"}
            </button>
            <button
              type="button"
              data-testid="reset-button"
              onClick={reset}
              disabled={busy}
              className="text-sm text-slate-500 hover:text-slate-700 disabled:opacity-50"
            >
              Start over
            </button>
          </div>
        </div>
      )}
    </Card>
  );
}
