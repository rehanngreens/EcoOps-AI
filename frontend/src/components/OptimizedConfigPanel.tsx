import { useState } from "react";
import type { OptimizedConfigResponse } from "../types/api";
import { Badge, Card, DisclaimerNote, Spinner } from "./ui/primitives";

function diffLineClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---")) return "text-slate-400";
  if (line.startsWith("@@")) return "text-sky-600";
  if (line.startsWith("+")) return "bg-eco-50 text-eco-700";
  if (line.startsWith("-")) return "bg-red-50 text-red-700";
  return "text-slate-600";
}

export function OptimizedConfigPanel({
  config,
  loading,
  error,
  onGenerate,
}: {
  config: OptimizedConfigResponse | null;
  loading: boolean;
  error: string | null;
  onGenerate: () => void;
}) {
  const [downloaded, setDownloaded] = useState(false);

  const download = () => {
    if (!config) return;
    const blob = new Blob([config.optimized_yaml], { type: "application/x-yaml" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "deployment-optimized.yaml";
    anchor.click();
    URL.revokeObjectURL(url);
    setDownloaded(true);
  };

  return (
    <Card title="Optimized configuration">
      {!config && !loading && !error && (
        <div>
          <p className="text-sm text-slate-500">
            Generate the optimized YAML from the accepted recommendation. Your original file is
            never modified.
          </p>
          <button
            type="button"
            onClick={onGenerate}
            data-testid="generate-config"
            className="mt-3 rounded-lg bg-eco-600 px-4 py-2 text-sm font-medium text-white hover:bg-eco-700"
          >
            Generate optimized YAML
          </button>
        </div>
      )}

      {loading && <Spinner label="Generating and round-trip validating the manifest…" />}

      {error && (
        <p className="text-sm text-slate-500" data-testid="config-unavailable">
          {error}
        </p>
      )}

      {config && !loading && (
        <div>
          <div className="mb-3 flex flex-wrap items-center gap-2">
            {config.changes.map((change, index) => (
              <Badge key={index} tone="improvement">
                {change.parameter}: {change.current} → {change.suggested}
              </Badge>
            ))}
          </div>

          <pre
            data-testid="diff-view"
            className="max-h-96 overflow-auto rounded-lg bg-slate-50 p-3 text-xs leading-relaxed"
          >
            {config.diff.map((line, index) => (
              <div key={index} className={`px-1 ${diffLineClass(line)}`}>
                {line || " "}
              </div>
            ))}
          </pre>

          <div className="mt-3 flex items-center gap-3">
            <button
              type="button"
              onClick={download}
              data-testid="download-config"
              className="rounded-lg bg-eco-600 px-4 py-2 text-sm font-medium text-white hover:bg-eco-700"
            >
              Download optimized YAML
            </button>
            {downloaded && (
              <span className="text-xs text-eco-700" data-testid="downloaded-note">
                Saved as deployment-optimized.yaml
              </span>
            )}
          </div>

          <DisclaimerNote text={config.disclaimer} />
        </div>
      )}
    </Card>
  );
}
