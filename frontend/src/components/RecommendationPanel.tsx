import type { OptimizeResponse } from "../types/api";
import { Badge, Card, DisclaimerNote, Spinner } from "./ui/primitives";
import { ScoreComparison } from "./ScoreCard";

export function RecommendationPanel({
  optimize,
  loading,
}: {
  optimize: OptimizeResponse | null;
  loading: boolean;
}) {
  if (loading) {
    return (
      <Card title="Recommendations">
        <Spinner label="Evaluating candidates through the constraint engine…" />
      </Card>
    );
  }

  if (!optimize) {
    return (
      <Card title="Recommendations">
        <p className="text-sm text-slate-500">
          Run the optimization to generate constraint-checked scale-down proposals.
        </p>
      </Card>
    );
  }

  const set = optimize.recommendation_set;

  if (set.status === "no_recommendation") {
    return (
      <Card title="Recommendations">
        <div className="mb-3" data-testid="no-recommendation">
          <Badge tone="neutral">No accepted recommendation</Badge>
          <p className="mt-2 text-sm text-slate-600">{set.explanation}</p>
        </div>
        {set.rejected_candidates.length > 0 && (
          <details className="mt-2">
            <summary className="cursor-pointer text-xs font-medium text-slate-500">
              {set.rejected_candidates.length} candidate(s) evaluated and rejected
            </summary>
            <ul className="mt-2 space-y-1" data-testid="rejected-list">
              {set.rejected_candidates.map((candidate, index) => (
                <li key={index} className="text-xs text-slate-500">
                  <span className="font-medium text-slate-700">{candidate.summary}</span> —{" "}
                  {candidate.reason}
                </li>
              ))}
            </ul>
          </details>
        )}
        <ScoreComparison
          baseline={optimize.scores.baseline.score}
          optimized={optimize.scores.baseline.score}
          improvement={0}
        />
        <DisclaimerNote text={set.disclaimer} />
      </Card>
    );
  }

  const totals = set.totals;

  return (
    <Card title="Recommendation">
      <div className="mb-3" data-testid="recommendation-status">
        <Badge tone="pass">Recommended</Badge>
        <p className="mt-2 text-sm text-slate-600">{set.explanation}</p>
      </div>

      <ul className="space-y-2" data-testid="recommendation-items">
        {set.items.map((item, index) => (
          <li key={index} className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
            <div className="flex items-center gap-2">
              <span className="font-medium capitalize text-slate-800">
                {item.parameter.replace(/_/g, " ")}
              </span>
              <span className="tabular-nums text-slate-500">
                {item.current_value} → <strong className="text-eco-700">{item.suggested_value}</strong>
              </span>
            </div>
            <p className="mt-0.5 text-xs text-slate-400">{item.reason}</p>
          </li>
        ))}
      </ul>

      {totals && (
        <div className="mt-4 grid grid-cols-3 gap-3" data-testid="savings">
          <div className="rounded-lg bg-eco-50 px-3 py-2">
            <p className="text-xs text-eco-700">Cost saved</p>
            <p className="text-base font-semibold tabular-nums text-eco-900">
              ${totals.cost_reduction_usd.toFixed(2)}
            </p>
          </div>
          <div className="rounded-lg bg-eco-50 px-3 py-2">
            <p className="text-xs text-eco-700">Energy saved</p>
            <p className="text-base font-semibold tabular-nums text-eco-900">
              {totals.energy_reduction_kwh.toFixed(1)} kWh
            </p>
          </div>
          <div className="rounded-lg bg-eco-50 px-3 py-2">
            <p className="text-xs text-eco-700">Carbon saved</p>
            <p className="text-base font-semibold tabular-nums text-eco-900">
              {totals.carbon_reduction_kg_co2e.toFixed(1)} kgCO₂e
            </p>
          </div>
        </div>
      )}

      {optimize.scores.optimized && (
        <div className="mt-4">
          <ScoreComparison
            baseline={optimize.scores.baseline.score}
            optimized={optimize.scores.optimized.score}
            improvement={optimize.scores.improvement ?? 0}
          />
        </div>
      )}

      {set.rejected_candidates.length > 0 && (
        <details className="mt-3">
          <summary className="cursor-pointer text-xs font-medium text-slate-500">
            {set.rejected_candidates.length} riskier candidate(s) rejected
          </summary>
          <ul className="mt-2 space-y-1" data-testid="rejected-list">
            {set.rejected_candidates.map((candidate, index) => (
              <li key={index} className="text-xs text-slate-500">
                <span className="font-medium text-slate-700">{candidate.summary}</span> —{" "}
                {candidate.reason}
              </li>
            ))}
          </ul>
        </details>
      )}

      <DisclaimerNote text={set.disclaimer} />
    </Card>
  );
}

export function RecommendationTrigger({
  onRun,
  busy,
  hasRun,
}: {
  onRun: () => void;
  busy: boolean;
  hasRun: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onRun}
      disabled={busy}
      data-testid="run-optimize"
      className="rounded-lg bg-eco-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-eco-700 disabled:opacity-50"
    >
      {hasRun ? "Re-run optimization" : "Run optimization"}
    </button>
  );
}
