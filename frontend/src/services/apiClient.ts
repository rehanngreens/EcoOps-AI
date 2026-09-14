import type {
  AnalyzeResponse,
  OptimizedConfigResponse,
  OptimizeResponse,
  ValidationResponse,
  WorkloadProfile,
} from "../types/api";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body; keep the generic message
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export async function analyzeManifest(
  yamlText: string,
  workload: WorkloadProfile | null,
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", new File([yamlText], "deployment.yaml", { type: "application/x-yaml" }));
  if (workload) {
    form.append("workload", JSON.stringify(workload));
  }
  const response = await fetch(`${API_BASE}/api/v1/analyze`, { method: "POST", body: form });
  return handleResponse<AnalyzeResponse>(response);
}

export async function validateManifest(yamlText: string): Promise<ValidationResponse> {
  const form = new FormData();
  form.append("file", new File([yamlText], "deployment.yaml", { type: "application/x-yaml" }));
  const response = await fetch(`${API_BASE}/api/v1/validate`, { method: "POST", body: form });
  return handleResponse<ValidationResponse>(response);
}

export async function fetchScore(analysisId: string) {
  const response = await fetch(`${API_BASE}/api/v1/analysis/${analysisId}/score`);
  return handleResponse<import("../types/api").AnalysisScoreResponse>(response);
}

export async function runOptimization(analysisId: string): Promise<OptimizeResponse> {
  const response = await fetch(`${API_BASE}/api/v1/analysis/${analysisId}/optimize`, {
    method: "POST",
  });
  return handleResponse<OptimizeResponse>(response);
}

export async function fetchOptimizedConfig(analysisId: string): Promise<OptimizedConfigResponse> {
  const response = await fetch(`${API_BASE}/api/v1/analysis/${analysisId}/optimized-config`);
  return handleResponse<OptimizedConfigResponse>(response);
}

/** Canonical demo workload profiles (must mirror backend test conventions). */
export interface DemoPreset {
  id: string;
  label: string;
  description: string;
  yaml: string;
  workload: WorkloadProfile;
}

import wellYaml from "../fixtures/deployment-well-provisioned.yaml?raw";
import moderateYaml from "../fixtures/deployment-moderate-overprovisioned.yaml?raw";
import heavyYaml from "../fixtures/deployment-heavy-overprovisioned.yaml?raw";

export const DEMO_PRESETS: DemoPreset[] = [
  {
    id: "well",
    label: "Well-provisioned",
    description: "2× 0.5c/512Mi — expect no recommendation",
    yaml: wellYaml,
    workload: {
      application_type: "rest-api",
      expected_users: 1000,
      traffic_level: "medium",
      max_latency_ms: 200,
      availability_target: 99.0,
    },
  },
  {
    id: "moderate",
    label: "Moderate overprovisioned",
    description: "4× 2c/4Gi, 10k users — borderline",
    yaml: moderateYaml,
    workload: {
      application_type: "web-application",
      expected_users: 10000,
      traffic_level: "medium",
      max_latency_ms: 150,
      availability_target: 99.9,
    },
  },
  {
    id: "heavy",
    label: "Heavy overprovisioned",
    description: "8× 8c/16Gi, 10k users — expect big savings",
    yaml: heavyYaml,
    workload: {
      application_type: "e-commerce",
      expected_users: 10000,
      traffic_level: "medium",
      max_latency_ms: 150,
      availability_target: 99.9,
    },
  },
];
