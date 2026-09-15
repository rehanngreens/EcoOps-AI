import { useState } from "react";
import type { WorkloadProfile } from "../types/api";
import { UploadPanel } from "../components/UploadPanel";
import { ErrorBanner, Spinner } from "../components/ui/primitives";
import { analyzeManifest } from "../services/apiClient";
import type { AnalyzeResponse } from "../types/api";

export function UploadPage({ onAnalyzed }: { onAnalyzed: (analysis: AnalyzeResponse) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyze = async (yaml: string, workload: WorkloadProfile, fileName?: string) => {
    setBusy(true);
    setError(null);
    try {
      const analysis = await analyzeManifest(yaml, workload, fileName);
      onAnalyzed(analysis);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Analysis failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="pt-10 text-center">
        <h1 className="text-3xl font-bold text-slate-900">
          EcoOps <span className="text-eco-600">AI</span>
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          Pre-deployment cloud sustainability advisor — analyze before you deploy, not after.
        </p>
      </header>

      {error && <ErrorBanner message={error} />}
      {busy && <Spinner label="Parsing, predicting, estimating…" />}
      <UploadPanel onAnalyze={analyze} busy={busy} />
    </div>
  );
}
