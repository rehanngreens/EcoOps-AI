import { useState } from "react";
import type { AnalyzeResponse } from "./types/api";
import { UploadPage } from "./pages/UploadPage";
import { DashboardPage } from "./pages/DashboardPage";

export default function App() {
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {analysis ? (
        <DashboardPage analysis={analysis} onReset={() => setAnalysis(null)} />
      ) : (
        <UploadPage onAnalyzed={setAnalysis} />
      )}
      <footer className="py-8 text-center text-xs text-slate-300">
        EcoOps AI prototype — all estimates are advisory and based on configurable assumptions.
      </footer>
    </div>
  );
}
