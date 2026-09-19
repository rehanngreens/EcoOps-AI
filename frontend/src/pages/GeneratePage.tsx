import { useState } from "react";
import type {
  GenerateResponse,
  WorkloadProfile,
} from "../types/api";
import {
  ApiError,
  generateInfrastructure,
} from "../services/apiClient";
import { ErrorBanner, Spinner } from "../components/ui/primitives";

const label = "block text-xs font-medium text-slate-600 mb-1";
const field =
  "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-eco-500 focus:outline-none";

const APPLICATION_TYPES = [
  "web-application",
  "e-commerce",
  "rest-api",
  "database",
  "machine-learning",
  "ai-inference",
  "streaming",
  "batch",
  "microservices",
] as const;

const TRAFFIC_PATTERNS = ["low", "medium", "high", "variable", "bursty"] as const;
const PRIORITIES = ["low", "medium", "high"] as const;
const TARGETS = [
  { value: "auto", label: "Let EcoOps AI choose (recommended)" },
  { value: "kubernetes", label: "Kubernetes" },
  { value: "terraform", label: "Terraform" },
  { value: "docker_compose", label: "Docker Compose" },
  { value: "terraform+kubernetes", label: "Terraform + Kubernetes" },
] as const;

const DEFAULT_GENERATION_WORKLOAD: WorkloadProfile = {
  application_type: "rest-api",
  expected_users: 2000,
  traffic_level: "medium",
  max_latency_ms: 250,
  availability_target: 99.9,
  average_rps: 200,
  peak_rps: 600,
  traffic_pattern: "variable",
  storage_gb: 50,
  autoscaling_required: false,
  performance_priority: "medium",
  cost_priority: "medium",
  sustainability_priority: "medium",
};

/** Design doc section 30, scenarios 4-5: workload-only Mode B demos. */
const DEMO_SCENARIO_WORKLOAD: WorkloadProfile = {
  ...DEFAULT_GENERATION_WORKLOAD,
  application_type: "e-commerce",
  expected_users: 10000,
  traffic_level: "high",
  max_latency_ms: 250,
  availability_target: 99.95,
  average_rps: 500,
  peak_rps: 2500,
  traffic_pattern: "bursty",
  storage_gb: 100,
  autoscaling_required: true,
  performance_priority: "high",
};

const GENERATION_DEMO_SCENARIOS = [
  {
    id: "scenario-4",
    label: "Scenario 4 — Let EcoOps AI choose",
    description:
      "Bursty e-commerce, 10,000 users, high availability, autoscaling required. " +
      "The target-selection rule fires visibly before candidates are evaluated.",
    target: "auto",
    workload: DEMO_SCENARIO_WORKLOAD,
  },
  {
    id: "scenario-5",
    label: "Scenario 5 — Explicit Kubernetes",
    description:
      "The same workload, but you pick Kubernetes explicitly. The generated " +
      "manifest round-trip parses back to the selected configuration.",
    target: "kubernetes",
    workload: DEMO_SCENARIO_WORKLOAD,
  },
] as const;

function download(filename: string, content: string) {
  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function GeneratePage({ onReset }: { onReset: () => void }) {
  const [workload, setWorkload] = useState<WorkloadProfile>(DEFAULT_GENERATION_WORKLOAD);
  const [target, setTarget] = useState<string>("auto");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [openArtifact, setOpenArtifact] = useState<string | null>(null);
  const [demoOpen, setDemoOpen] = useState(false);

  const update = <K extends keyof WorkloadProfile>(key: K, value: WorkloadProfile[K]) =>
    setWorkload((current) => ({ ...current, [key]: value }));

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const response = await generateInfrastructure(workload, target === "auto" ? null : target);
      setResult(response);
      setOpenArtifact(response.artifacts[0]?.filename ?? null);
    } catch (cause) {
      setResult(null);
      if (cause instanceof ApiError && cause.status === 422) {
        setError(
          `No candidate satisfied your constraints, so nothing was generated. ${cause.message}`,
        );
      } else {
        setError(cause instanceof Error ? cause.message : "Generation failed");
      }
    } finally {
      setBusy(false);
    }
  };

  if (result) {
    const winner = result.evaluation.selected_index != null
      ? result.evaluation.candidates[result.evaluation.selected_index]
      : null;
    const rejected = result.evaluation.candidates.filter((candidate) => !candidate.eligible);

    return (
      <div className="mx-auto max-w-4xl space-y-6" data-testid="generation-result">
        <header className="pt-10">
          <h1 className="text-2xl font-bold text-slate-900">Recommended infrastructure</h1>
          <p className="mt-1 text-sm text-slate-500">
            Generation <code className="text-xs">{result.generation_id}</code> — prototype for
            review; nothing is deployed.
          </p>
        </header>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Architecture summary
          </h2>
          <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4" data-testid="architecture-summary">
            <div><dt className="text-slate-500">Application</dt><dd className="font-medium">{result.selected_configuration?.application}</dd></div>
            <div><dt className="text-slate-500">CPU / replica</dt><dd className="font-medium">{result.selected_configuration?.cpu_request} cores</dd></div>
            <div><dt className="text-slate-500">Memory / replica</dt><dd className="font-medium">{result.selected_configuration?.memory_request_gb} GiB</dd></div>
            <div><dt className="text-slate-500">Replicas</dt><dd className="font-medium">{result.selected_configuration?.replicas}{result.selected_configuration?.autoscaling_enabled ? " (autoscaling)" : ""}</dd></div>
            {result.selected_configuration?.storage_gb != null && (
              <div><dt className="text-slate-500">Storage</dt><dd className="font-medium">{result.selected_configuration.storage_gb} GB</dd></div>
            )}
            {result.selected_configuration?.instance_type && (
              <div><dt className="text-slate-500">Instance type</dt><dd className="font-medium">{result.selected_configuration.instance_type}</dd></div>
            )}
            {result.selected_configuration?.cloud_provider && (
              <div><dt className="text-slate-500">Cloud / region</dt><dd className="font-medium">{result.selected_configuration.cloud_provider}{result.selected_configuration.region ? ` · ${result.selected_configuration.region}` : ""}</dd></div>
            )}
            <div><dt className="text-slate-500">Target</dt><dd className="font-medium">{result.target_selection.target}{result.target_selection.source === "auto" ? " (auto)" : ""}</dd></div>
          </dl>
          {result.target_selection.source === "auto" && (
            <p className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600" data-testid="target-explanation">
              {result.target_selection.explanation}
            </p>
          )}
        </section>

        {winner && (
          <section className="rounded-xl border border-eco-200 bg-eco-50 p-5">
            <h2 className="text-sm font-semibold text-eco-800">
              Why this configuration? — score {winner.score.score.toFixed(4)} ({winner.score.grade})
            </h2>
            <p className="mt-2 text-sm text-slate-700">{winner.plan.summary}</p>
            <p className="mt-2 text-xs text-slate-600">{result.evaluation.ranking_explanation}</p>
            <ul className="mt-2 space-y-1 text-xs text-slate-500">
              {winner.estimation.disclaimer && <li>{winner.estimation.disclaimer}</li>}
            </ul>
          </section>
        )}

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Estimated impact (per period — heuristic estimates, not guarantees)
          </h2>
          {winner && (
            <dl className="mt-3 grid grid-cols-3 gap-3 text-sm">
              <div><dt className="text-slate-500">Cost</dt><dd className="font-medium">${winner.estimation.estimated_cost_usd.toFixed(2)}</dd></div>
              <div><dt className="text-slate-500">Energy</dt><dd className="font-medium">{winner.estimation.estimated_energy_kwh.toFixed(1)} kWh</dd></div>
              <div><dt className="text-slate-500">Carbon</dt><dd className="font-medium">{winner.estimation.estimated_carbon_kg_co2e.toFixed(1)} kgCO₂e</dd></div>
            </dl>
          )}
        </section>

        {rejected.length > 0 && (
          <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm text-sm" data-testid="rejected-candidates">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
              Rejected candidates ({rejected.length}) — evaluated but ineligible
            </h2>
            <ul className="mt-2 space-y-2">
              {rejected.map((candidate) => (
                <li key={candidate.plan.variant}>
                  <span className="font-medium">{candidate.plan.variant}</span>
                  <span className="text-slate-500"> — {candidate.rejection_reasons.length} failed check(s)</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">
            Generated configuration ({result.artifacts.length} file{result.artifacts.length === 1 ? "" : "s"})
          </h2>
          <div className="mt-3 space-y-3" data-testid="artifact-list">
            {result.artifacts.map((artifact) => (
              <div key={artifact.filename} className="rounded-lg border border-slate-200">
                <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-3 py-2">
                  <button
                    type="button"
                    className="text-sm font-medium text-slate-800 hover:text-eco-700"
                    onClick={() => setOpenArtifact(openArtifact === artifact.filename ? null : artifact.filename)}
                  >
                    {openArtifact === artifact.filename ? "▾" : "▸"} {artifact.filename}
                    <span className="ml-2 rounded bg-eco-100 px-1.5 py-0.5 text-[10px] font-semibold text-eco-800">
                      validated
                    </span>
                  </button>
                  <button
                    type="button"
                    className="rounded-lg border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
                    onClick={() => download(artifact.filename, artifact.content)}
                  >
                    Download
                  </button>
                </div>
                {openArtifact === artifact.filename && (
                  <pre data-testid={`artifact-preview-${artifact.filename}`} className="max-h-96 overflow-auto p-3 text-xs leading-relaxed text-slate-700">
                    {artifact.content}
                  </pre>
                )}
                {openArtifact === artifact.filename && artifact.notes.map((note) => (
                  <p key={note} className="border-t border-slate-100 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                    Note: {note}
                  </p>
                ))}
              </div>
            ))}
          </div>
        </section>

        <button
          type="button"
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-white"
          onClick={() => { setResult(null); onReset(); }}
        >
          Start a new generation
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6" data-testid="generate-page">
      <header className="pt-10 text-center">
        <h1 className="text-2xl font-bold text-slate-900">Create sustainable infrastructure</h1>
        <p className="mt-2 text-sm text-slate-500">
          Describe your workload — no IaC knowledge needed. EcoOps AI designs candidates,
          checks constraints, and generates the configuration for you to review.
        </p>
      </header>

      {error && <ErrorBanner message={error} />}

      {/* Guided demo scenarios (design doc section 30, scenarios 4-5). */}
      <div data-testid="generation-demo-section">
        {!demoOpen ? (
          <button
            type="button"
            data-testid="generation-demo-enter"
            disabled={busy}
            onClick={() => setDemoOpen(true)}
            className="rounded-lg border border-eco-200 bg-eco-50 px-4 py-2 text-sm font-medium text-eco-700 transition-colors hover:bg-eco-100 disabled:opacity-50"
          >
            Try a guided generation demo →
          </button>
        ) : (
          <div
            data-testid="generation-demo-browser"
            className="rounded-lg border border-slate-200 bg-slate-50/60 p-4"
          >
            <div className="flex items-center justify-between">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
                Generation demo scenarios
              </p>
              <button
                type="button"
                data-testid="generation-demo-close"
                onClick={() => setDemoOpen(false)}
                className="text-xs font-medium text-slate-500 hover:text-slate-700"
              >
                Close
              </button>
            </div>
            <p className="mt-2 text-sm font-medium text-slate-700">
              Choose a workload-only scenario — the form is pre-filled and editable.
            </p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {GENERATION_DEMO_SCENARIOS.map((scenario) => (
                <button
                  key={scenario.id}
                  type="button"
                  data-testid={`generation-preset-${scenario.id}`}
                  disabled={busy}
                  onClick={() => {
                    setWorkload(scenario.workload);
                    setTarget(scenario.target);
                    setDemoOpen(false);
                  }}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-3 text-left transition-colors hover:border-eco-500 hover:bg-eco-50 disabled:opacity-50"
                >
                  <span className="block text-sm font-medium text-slate-800">
                    {scenario.label}
                  </span>
                  <span className="mt-0.5 block text-xs text-slate-400">
                    {scenario.description}
                  </span>
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Workload requirements</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="gen-type" className={label}>Application type</label>
            <select id="gen-type" className={field} value={workload.application_type}
              onChange={(event) => update("application_type", event.target.value)}>
              {APPLICATION_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="gen-users" className={label}>Expected users</label>
            <input id="gen-users" type="number" min={0} className={field} value={workload.expected_users}
              onChange={(event) => update("expected_users", Number(event.target.value))} />
          </div>
          <div>
            <label htmlFor="gen-avg-rps" className={label}>Average requests / second</label>
            <input id="gen-avg-rps" type="number" min={0} step="any" className={field} value={workload.average_rps ?? ""}
              onChange={(event) => update("average_rps", event.target.value === "" ? null : Number(event.target.value))} />
          </div>
          <div>
            <label htmlFor="gen-peak-rps" className={label}>Peak requests / second</label>
            <input id="gen-peak-rps" type="number" min={0} step="any" className={field} value={workload.peak_rps ?? ""}
              onChange={(event) => update("peak_rps", event.target.value === "" ? null : Number(event.target.value))} />
          </div>
          <div>
            <label htmlFor="gen-pattern" className={label}>Traffic pattern</label>
            <select id="gen-pattern" className={field} value={workload.traffic_pattern ?? "medium"}
              onChange={(event) => update("traffic_pattern", event.target.value)}>
              {TRAFFIC_PATTERNS.map((pattern) => <option key={pattern} value={pattern}>{pattern}</option>)}
            </select>
          </div>
          <div>
            <label htmlFor="gen-latency" className={label}>Max acceptable latency (ms)</label>
            <input id="gen-latency" type="number" min={1} className={field} value={workload.max_latency_ms}
              onChange={(event) => update("max_latency_ms", Number(event.target.value))} />
          </div>
          <div>
            <label htmlFor="gen-availability" className={label}>Availability requirement (%)</label>
            <input id="gen-availability" type="number" min={0} max={100} step="0.01" className={field}
              value={workload.availability_target}
              onChange={(event) => update("availability_target", Number(event.target.value))} />
          </div>
          <div>
            <label htmlFor="gen-storage" className={label}>Storage requirement (GB, optional)</label>
            <input id="gen-storage" type="number" min={0} step="any" className={field} value={workload.storage_gb ?? ""}
              onChange={(event) => update("storage_gb", event.target.value === "" ? null : Number(event.target.value))} />
          </div>
          <div className="flex items-center gap-2">
            <input id="gen-autoscaling" type="checkbox" className="h-4 w-4" checked={workload.autoscaling_required ?? false}
              onChange={(event) => update("autoscaling_required", event.target.checked)} />
            <label htmlFor="gen-autoscaling" className="text-sm text-slate-700">Autoscaling required</label>
          </div>
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Priorities</h2>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          {(["performance_priority", "cost_priority", "sustainability_priority"] as const).map((key) => (
            <div key={key}>
              <label htmlFor={`gen-${key}`} className={label}>
                {key.replace("_priority", "").replace(/^\w/, (c) => c.toUpperCase())} priority
              </label>
              <select id={`gen-${key}`} className={field} value={workload[key] ?? "medium"}
                onChange={(event) => update(key, event.target.value)}>
                {PRIORITIES.map((priority) => <option key={priority} value={priority}>{priority}</option>)}
              </select>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">IaC generation target</h2>
        <div className="mt-4">
          <label htmlFor="gen-target" className={label}>Generate configuration for</label>
          <select id="gen-target" className={field} value={target} onChange={(event) => setTarget(event.target.value)}>
            {TARGETS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </div>
      </section>

      <div className="flex items-center justify-between">
        <button type="button" className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-white" onClick={onReset}>
          ← Back
        </button>
        <button
          type="button"
          className="rounded-lg bg-eco-600 px-6 py-2.5 text-sm font-semibold text-white hover:bg-eco-700 disabled:opacity-50"
          onClick={submit}
          disabled={busy}
          data-testid="generate-submit"
        >
          {busy ? "Designing candidates…" : "Generate infrastructure"}
        </button>
      </div>

      {busy && <Spinner label="Estimating requirements, evaluating candidates, rendering IaC…" />}
    </div>
  );
}
