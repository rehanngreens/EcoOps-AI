import { useRef, useState } from "react";
import { DEMO_PRESETS, type DemoPreset } from "../services/apiClient";
import { Card } from "./ui/primitives";

export function UploadPanel({
  onAnalyze,
  busy,
}: {
  onAnalyze: (yaml: string, workload: DemoPreset["workload"] | null) => void;
  busy: boolean;
}) {
  const [dragOver, setDragOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const readFile = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => onAnalyze(String(reader.result), null);
    reader.readAsText(file);
  };

  return (
    <Card title="Analyze a Kubernetes deployment">
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
        className={`cursor-pointer rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors ${
          dragOver
            ? "border-eco-500 bg-eco-50"
            : "border-slate-300 hover:border-eco-500 hover:bg-eco-50/50"
        }`}
      >
        <p className="text-sm font-medium text-slate-700">
          Drag &amp; drop a Kubernetes YAML here
        </p>
        <p className="mt-1 text-xs text-slate-400">or click to browse (.yaml / .yml)</p>
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

      <p className="mt-6 text-xs font-semibold uppercase tracking-wide text-slate-400">
        Or try a demo scenario
      </p>
      <div className="mt-2 grid gap-2 sm:grid-cols-3">
        {DEMO_PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            disabled={busy}
            data-testid={`preset-${preset.id}`}
            onClick={() => onAnalyze(preset.yaml, preset.workload)}
            className="rounded-lg border border-slate-200 px-3 py-2 text-left transition-colors hover:border-eco-500 hover:bg-eco-50 disabled:opacity-50"
          >
            <span className="block text-sm font-medium text-slate-800">{preset.label}</span>
            <span className="block text-xs text-slate-400">{preset.description}</span>
          </button>
        ))}
      </div>
    </Card>
  );
}
