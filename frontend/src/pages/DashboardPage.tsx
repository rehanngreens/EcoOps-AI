import { useState } from "react";
import type { AnalyzeResponse, OptimizedConfigResponse, OptimizeResponse } from "../types/api";
import { fetchOptimizedConfig, fetchScore, runOptimization } from "../services/apiClient";
import {
  ConfigurationPanel,
  EstimateCards,
  ProblemsPanel,
  UtilizationChart,
} from "../components/OverviewPanels";
import { ScoreCard } from "../components/ScoreCard";
import {
  RecommendationPanel,
  RecommendationTrigger,
} from "../components/RecommendationPanel";
import { OptimizedConfigPanel } from "../components/OptimizedConfigPanel";
import { Card, ErrorBanner, Spinner } from "../components/ui/primitives";
import type { SustainabilityScore } from "../types/api";
import { useEffect } from "react";

export function DashboardPage({
  analysis,
  onReset,
}: {
  analysis: AnalyzeResponse;
  onReset: () => void;
}) {
  const [score, setScore] = useState<SustainabilityScore | null>(null);
  const [optimize, setOptimize] = useState<OptimizeResponse | null>(null);
  const [optimizeBusy, setOptimizeBusy] = useState(false);
  const [optimizedConfig, setOptimizedConfig] = useState<OptimizedConfigResponse | null>(null);
  const [configBusy, setConfigBusy] = useState(false);
  const [configError, setConfigError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchScore(analysis.analysis_id)
      .then((response) => {
        if (!cancelled) setScore(response.score);
      })
      .catch(() => {
        /* score is optional enrichment; estimate cards still show */
      });
    return () => {
      cancelled = true;
    };
  }, [analysis.analysis_id]);

  const handleOptimize = async () => {
    setOptimizeBusy(true);
    try {
      const result = await runOptimization(analysis.analysis_id);
      setOptimize(result);
      setOptimizedConfig(null);
      setConfigError(null);
    } catch (cause) {
      setConfigError(cause instanceof Error ? cause.message : "Optimization failed");
    } finally {
      setOptimizeBusy(false);
    }
  };

  const handleGenerateConfig = async () => {
    setConfigBusy(true);
    setConfigError(null);
    try {
      setOptimizedConfig(await fetchOptimizedConfig(analysis.analysis_id));
    } catch (cause) {
      setConfigError(
        cause instanceof Error ? cause.message : "Could not generate optimized configuration",
      );
    } finally {
      setConfigBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <header className="flex items-center justify-between pt-8">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">
            {analysis.configuration.application}
            <span className="ml-2 text-sm font-normal text-slate-400">
              {analysis.configuration.namespace}
            </span>
          </h1>
          <p className="text-xs text-slate-400">Analysis {analysis.analysis_id}</p>
        </div>
        <button
          type="button"
          onClick={onReset}
          data-testid="new-analysis"
          className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
        >
          New analysis
        </button>
      </header>

      {configError && <ErrorBanner message={configError} />}

      <div className="grid gap-5 lg:grid-cols-2">
        {score ? (
          <ScoreCard score={score} />
        ) : (
          <Card title="Sustainability score">
            <Spinner label="Computing score…" />
          </Card>
        )}
        <UtilizationChart analysis={analysis} />
        <EstimateCards analysis={analysis} />
        <ConfigurationPanel analysis={analysis} />
        <ProblemsPanel analysis={analysis} />
      </div>

      <Card title="Optimization">
        <RecommendationTrigger
          onRun={handleOptimize}
          busy={optimizeBusy}
          hasRun={optimize !== null}
        />
      </Card>

      <RecommendationPanel optimize={optimize} loading={optimizeBusy} />

      {optimize?.recommendation_set.status === "recommended" && (
        <OptimizedConfigPanel
          config={optimizedConfig}
          loading={configBusy}
          error={configError}
          onGenerate={handleGenerateConfig}
        />
      )}
    </div>
  );
}
