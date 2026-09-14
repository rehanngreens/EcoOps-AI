import type { WorkloadProfile } from "../types/api";

export const APPLICATION_TYPES = [
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

export const TRAFFIC_LEVELS = ["low", "medium", "high", "variable"] as const;

/** Backend defaults (WorkloadProfile in backend/app/schemas/workload_schema.py). */
export const DEFAULT_WORKLOAD: WorkloadProfile = {
  application_type: "rest-api",
  expected_users: 1000,
  traffic_level: "medium",
  max_latency_ms: 200,
  availability_target: 99.0,
};

const label = "block text-xs font-medium text-slate-600 mb-1";
const field =
  "w-full rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800 focus:border-eco-500 focus:outline-none";

export function WorkloadForm({
  workload,
  onChange,
}: {
  workload: WorkloadProfile;
  onChange: (next: WorkloadProfile) => void;
}) {
  const update = <K extends keyof WorkloadProfile>(key: K, value: WorkloadProfile[K]) =>
    onChange({ ...workload, [key]: value });

  return (
    <div data-testid="workload-form" className="grid gap-4 sm:grid-cols-2">
      <div>
        <label htmlFor="wl-type" className={label}>
          Application type
        </label>
        <select
          id="wl-type"
          className={field}
          value={workload.application_type}
          onChange={(event) => update("application_type", event.target.value)}
        >
          {APPLICATION_TYPES.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="wl-users" className={label}>
          Expected users
        </label>
        <input
          id="wl-users"
          type="number"
          min={0}
          className={field}
          value={workload.expected_users}
          onChange={(event) => update("expected_users", Number(event.target.value))}
        />
      </div>

      <div>
        <label htmlFor="wl-traffic" className={label}>
          Traffic level
        </label>
        <select
          id="wl-traffic"
          className={field}
          value={workload.traffic_level}
          onChange={(event) =>
            update("traffic_level", event.target.value as WorkloadProfile["traffic_level"])
          }
        >
          {TRAFFIC_LEVELS.map((level) => (
            <option key={level} value={level}>
              {level}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label htmlFor="wl-latency" className={label}>
          Max latency (ms)
        </label>
        <input
          id="wl-latency"
          type="number"
          min={1}
          className={field}
          value={workload.max_latency_ms}
          onChange={(event) => update("max_latency_ms", Number(event.target.value))}
        />
      </div>

      <div>
        <label htmlFor="wl-availability" className={label}>
          Availability target (%)
        </label>
        <input
          id="wl-availability"
          type="number"
          min={0}
          max={100}
          step={0.01}
          className={field}
          value={workload.availability_target}
          onChange={(event) => update("availability_target", Number(event.target.value))}
        />
      </div>
    </div>
  );
}
