import { useRef, useState } from "react";
import type { WorkloadProfile } from "../types/api";
import { DEMO_PRESETS, type DemoPreset } from "../services/apiClient";
import { Card } from "./ui/primitives";
import { DEFAULT_WORKLOAD, WorkloadForm } from "./WorkloadForm";

type StagedFile = { name: string; yaml: string } | null;

export function UploadPanel({
  onAnalyze,
  busy,
}: {
  onAnalyze: (yaml: string, workload: WorkloadProfile) => void;
  busy: boolean;
}) {
  const [staged, setStaged] = useState<StagedFile>(null);
  const [workload, setWorkload] = useState<WorkloadProfile>(DEFAULT_WORKLOAD);
  const [presetId, setPresetId] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const stageFile = (name: string, yaml: string, preset: DemoPreset | null) => {
    setStaged({ name, yaml });
    setPresetId(preset?.id ?? null);
    if (preset) {
      setWorkload(preset.workload);
    } else if (staged === null) {
      setWorkload(DEFAULT_WORKLOAD);
    }
  };

  const readFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => stageFile(file.name, String(reader.result), null);
    reader.readAsText(file);
  };

  const runAnalysis = () => {
    if (!staged) return;
    onAnalyze(staged.yaml, workload);
  };

  return (
    <Card title="Analyze a Kubernetes deployment">
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
              Drag &amp; drop a Kubernetes YAML here
            </p>
            <p className="mt-1 text-xs text-slate-400">or click to browse (.yaml / .yml)</p>
          </>
        )}
        <input
          ref={fileInput}
          type="file"
          accept=".yaml,.yml"
          className="hidden"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) readFile(file);
          }}
        />
      </div>

      {/* Demo presets stage a manifest AND its canonical workload in one click. */}
      {!staged && (
        <>
          <p className="mt-6 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Or start from a demo scenario
          </p>
          <div className="mt-2 grid gap-2 sm:grid-cols-3">
            {DEMO_PRESETS.map((preset) => (
              <button
                key={preset.id}
                type="button"
                disabled={busy}
                data-testid={`preset-${preset.id}`}
                onClick={() => stageFile(`${preset.id}-deployment.yaml`, preset.yaml, preset)}
                className="rounded-lg border border-slate-200 px-3 py-2 text-left transition-colors hover:border-eco-500 hover:bg-eco-50 disabled:opacity-50"
              >
                <span className="block text-sm font-medium text-slate-800">{preset.label}</span>
                <span className="block text-xs text-slate-400">{preset.description}</span>
              </button>
            ))}
          </div>
        </>
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
              onClick={() => {
                setStaged(null);
                setPresetId(null);
                setWorkload(DEFAULT_WORKLOAD);
              }}
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
