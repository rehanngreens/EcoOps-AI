import type { SustainabilityScore } from "../types/api";
import { Badge, Card, DisclaimerNote } from "./ui/primitives";

const GRADE_TONES: Record<string, "pass" | "fail" | "neutral"> = {
  A: "pass",
  B: "pass",
  C: "neutral",
  D: "fail",
  F: "fail",
};

export function ScoreCard({ score, title }: { score: SustainabilityScore; title?: string }) {
  return (
    <Card title={title ?? "Sustainability score"}>
      <div className="flex items-center gap-4">
        <span
          data-testid="score-value"
          className="text-4xl font-bold tabular-nums text-slate-900"
        >
          {score.score.toFixed(2)}
        </span>
        <span
          data-testid="score-grade"
          className={`flex h-12 w-12 items-center justify-center rounded-xl text-2xl font-bold ${
            GRADE_TONES[score.grade] === "pass"
              ? "bg-eco-100 text-eco-700"
              : GRADE_TONES[score.grade] === "fail"
                ? "bg-red-100 text-red-700"
                : "bg-amber-100 text-amber-700"
          }`}
        >
          {score.grade}
        </span>
      </div>

      <div className="mt-4 space-y-2">
        {score.components.map((component) => (
          <div key={component.name} title={component.explanation}>
            <div className="flex justify-between text-xs text-slate-600">
              <span className="capitalize">
                {component.name.replace(/_/g, " ")}
                <span className="ml-1 text-slate-400">({Math.round(component.weight * 100)}%)</span>
              </span>
              <span className="tabular-nums text-slate-500">{component.raw_value}</span>
            </div>
            <div className="mt-1 h-1.5 w-full rounded-full bg-slate-100">
              <div
                data-testid={`bar-${component.name}`}
                className={`h-1.5 rounded-full ${
                  component.score >= 0.7
                    ? "bg-eco-500"
                    : component.score >= 0.4
                      ? "bg-amber-400"
                      : "bg-red-400"
                }`}
                style={{ width: `${Math.round(component.score * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>

      <DisclaimerNote text={score.disclaimer} methodology={score.methodology} />
    </Card>
  );
}

export function ScoreComparison({
  baseline,
  optimized,
  improvement,
}: {
  baseline: number;
  optimized: number;
  improvement: number;
}) {
  return (
    <Card title="Score: current vs optimized">
      <div className="flex items-center gap-6">
        <div>
          <p className="text-xs text-slate-400">Current</p>
          <p className="text-2xl font-bold tabular-nums" data-testid="baseline-score">
            {baseline.toFixed(2)}
          </p>
        </div>
        <span className="text-slate-300">→</span>
        <div>
          <p className="text-xs text-slate-400">Optimized</p>
          <p className="text-2xl font-bold tabular-nums text-eco-700" data-testid="optimized-score">
            {optimized.toFixed(2)}
          </p>
        </div>
        <Badge tone="improvement">
          {improvement >= 0 ? "+" : ""}
          {improvement.toFixed(2)}
        </Badge>
      </div>
    </Card>
  );
}
