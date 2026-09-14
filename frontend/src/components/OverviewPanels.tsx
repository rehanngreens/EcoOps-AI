import {
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import type { AnalyzeResponse } from "../types/api";
import { Badge, Card, DisclaimerNote } from "./ui/primitives";

export function EstimateCards({ analysis }: { analysis: AnalyzeResponse }) {
  const { estimation } = analysis;
  const stats = [
    { label: "Est. cost / period", value: `$${estimation.estimated_cost_usd.toFixed(2)}` },
    { label: "Est. energy / period", value: `${estimation.estimated_energy_kwh.toFixed(1)} kWh` },
    {
      label: "Est. carbon / period",
      value: `${estimation.estimated_carbon_kg_co2e.toFixed(1)} kgCO₂e`,
    },
  ];
  return (
    <Card title="Estimates (transparent, configurable assumptions)">
      <div className="grid grid-cols-3 gap-3">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-lg bg-slate-50 px-3 py-3">
            <p className="text-xs text-slate-400">{stat.label}</p>
            <p className="mt-1 text-lg font-semibold tabular-nums text-slate-900" data-testid={stat.label.startsWith("Est. cost") ? "est-cost" : stat.label.startsWith("Est. energy") ? "est-energy" : "est-carbon"}>
              {stat.value}
            </p>
          </div>
        ))}
      </div>
      <DisclaimerNote text={estimation.disclaimer} />
    </Card>
  );
}

export function UtilizationChart({ analysis }: { analysis: AnalyzeResponse }) {
  const data = [
    { name: "CPU", value: Math.round(analysis.prediction.cpu_utilization * 100), fill: "#10b981" },
    { name: "Memory", value: Math.round(analysis.prediction.memory_utilization * 100), fill: "#0ea5e9" },
  ];
  return (
    <Card title="Predicted utilization">
      <div className="mx-auto h-40 w-full max-w-sm">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            data={data}
            innerRadius="30%"
            outerRadius="100%"
            startAngle={90}
            endAngle={-270}
          >
            <RadialBar dataKey="value" background cornerRadius={8} />
            <Tooltip formatter={(value: number) => `${value}%`} />
          </RadialBarChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 flex justify-center gap-6 text-sm">
        {data.map((entry) => (
          <span key={entry.name} className="flex items-center gap-2 text-slate-600">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: entry.fill }} />
            {entry.name} <strong className="tabular-nums">{entry.value}%</strong>
          </span>
        ))}
      </div>
    </Card>
  );
}

export function ConfigurationPanel({ analysis }: { analysis: AnalyzeResponse }) {
  const config = analysis.configuration;
  const rows: Array<[string, string]> = [
    ["Application", `${config.application} (${config.namespace})`],
    ["Replicas", String(config.replicas)],
    ["CPU request", config.cpu_request != null ? `${config.cpu_request} cores` : "—"],
    ["CPU limit", config.cpu_limit != null ? `${config.cpu_limit} cores` : "—"],
    ["Memory request", config.memory_request_gb != null ? `${config.memory_request_gb} GiB` : "—"],
    ["Memory limit", config.memory_limit_gb != null ? `${config.memory_limit_gb} GiB` : "—"],
    ["Autoscaling", config.autoscaling_enabled ? "Enabled" : "Disabled"],
    [
      "Workload",
      `${analysis.workload.application_type}, ${analysis.workload.expected_users.toLocaleString()} users, ${analysis.workload.traffic_level} traffic`,
    ],
  ];
  return (
    <Card title="Current configuration">
      <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
        {rows.map(([label, value]) => (
          <div key={label} className="flex justify-between border-b border-slate-100 py-1">
            <dt className="text-slate-400">{label}</dt>
            <dd className="font-medium text-slate-800">{value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

export function ProblemsPanel({ analysis }: { analysis: AnalyzeResponse }) {
  const failed = analysis.constraints.checks.filter((check) => check.status === "fail");
  return (
    <Card title="Problems detected">
      {failed.length === 0 ? (
        <p className="text-sm text-slate-500" data-testid="no-problems">
          No feasibility problems detected — all constraint checks pass.
        </p>
      ) : (
        <ul className="space-y-2" data-testid="problem-list">
          {failed.map((check) => (
            <li key={check.name} className="flex items-start gap-2 text-sm">
              <Badge tone="fail">{check.name.replace(/_/g, " ")}</Badge>
              <span className="text-slate-600">{check.explanation}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
