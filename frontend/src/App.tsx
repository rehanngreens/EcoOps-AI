import { useState } from "react";
import type { AnalyzeResponse } from "./types/api";
import { DashboardPage } from "./pages/DashboardPage";
import { GeneratePage } from "./pages/GeneratePage";
import { UploadPage } from "./pages/UploadPage";

type Mode = "landing" | "analyze" | "generate";

export default function App() {
  const [mode, setMode] = useState<Mode>("landing");
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);

  if (analysis) {
    return (
      <div className="min-h-screen bg-slate-50 text-slate-900">
        <DashboardPage analysis={analysis} onReset={() => { setAnalysis(null); setMode("landing"); }} />
        <footer className="py-8 text-center text-xs text-slate-300">
          EcoOps AI prototype — all estimates are advisory and based on configurable assumptions.
        </footer>
      </div>
    );
  }

  if (mode === "analyze") {
    return (
      <div className="min-h-screen bg-slate-50 text-slate-900">
        <UploadPage
          onAnalyzed={setAnalysis}
          onBack={() => setMode("landing")}
        />
        <footer className="py-8 text-center text-xs text-slate-300">
          EcoOps AI prototype — all estimates are advisory and based on configurable assumptions.
        </footer>
      </div>
    );
  }

  if (mode === "generate") {
    return (
      <div className="min-h-screen bg-slate-50 text-slate-900">
        <GeneratePage onReset={() => setMode("landing")} />
        <footer className="py-8 text-center text-xs text-slate-300">
          EcoOps AI prototype — all estimates are advisory and based on configurable assumptions.
        </footer>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <div className="mx-auto max-w-3xl px-4 py-16 text-center" data-testid="landing">
        <h1 className="text-4xl font-bold text-slate-900">
          EcoOps <span className="text-eco-600">AI</span>
        </h1>
        <p className="mx-auto mt-3 max-w-xl text-sm text-slate-500">
          An AI-powered pre-deployment cloud sustainability advisor. Analyze an existing
          Infrastructure as Code configuration — or design one from workload requirements.
        </p>

        <h2 className="mt-12 text-sm font-semibold uppercase tracking-wide text-slate-400">
          What do you want to do?
        </h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <button
            type="button"
            data-testid="entry-analyze"
            className="group rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:border-eco-300 hover:shadow-md"
            onClick={() => setMode("analyze")}
          >
            <span className="block text-lg font-semibold text-slate-900 group-hover:text-eco-700">
              Analyze existing infrastructure
            </span>
            <span className="mt-2 block text-sm text-slate-500">
              You already have Terraform, Kubernetes, or Docker Compose files. Upload them,
              add your workload, and get predictions, sustainability scores, and an
              optimized version.
            </span>
          </button>

          <button
            type="button"
            data-testid="entry-generate"
            className="group rounded-2xl border border-slate-200 bg-white p-6 text-left shadow-sm transition hover:border-eco-300 hover:shadow-md"
            onClick={() => setMode("generate")}
          >
            <span className="block text-lg font-semibold text-slate-900 group-hover:text-eco-700">
              Create sustainable infrastructure
            </span>
            <span className="mt-2 block text-sm text-slate-500">
              You only know your application and workload requirements. Describe them in a
              form — no IaC syntax needed — and get candidate designs, impact estimates, and
              a generated configuration to review and download.
            </span>
          </button>
        </div>
      </div>
      <footer className="py-8 text-center text-xs text-slate-300">
        EcoOps AI prototype — all estimates are advisory and based on configurable assumptions.
      </footer>
    </div>
  );
}
