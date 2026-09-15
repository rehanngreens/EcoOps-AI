import type {
  AnalyzeResponse,
  GenerateResponse,
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
      else if (body?.detail && typeof body?.detail === "object")
        return (await response.json()) as T; // handled by callers (infeasible 422)
    } catch {
      // non-JSON error body; keep the generic message
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export async function generateInfrastructure(
  workload: WorkloadProfile,
  target: string | null,
): Promise<GenerateResponse> {
  const response = await fetch(`${API_BASE}/api/v1/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workload, target }),
  });
  if (!response.ok) {
    // The 422 infeasible path returns a structured object detail.
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    if (response.status === 422 && detail && typeof detail === "object") {
      const err = new ApiError(422, detail.explanation ?? "Infeasible generation");
      (err as ApiError & { infeasible?: unknown }).infeasible = detail;
      throw err;
    }
    const message =
      typeof detail === "string" ? detail : `Generation failed (${response.status})`;
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as GenerateResponse;
}

export async function analyzeManifest(
  yamlText: string,
  workload: WorkloadProfile | null,
  fileName = "deployment.yaml",
): Promise<AnalyzeResponse> {
  const form = new FormData();
  const isTerraform = fileName.endsWith(".tf");
  form.append(
    "file",
    new File([yamlText], fileName, {
      type: isTerraform ? "text/x-terraform" : "application/x-yaml",
    }),
  );
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
  /** The IaC text (YAML, Terraform, or Compose) staged for analysis. */
  yaml: string;
  /** File name used when staging and sending the demo. */
  fileName: string;
  /** IaC family, used to group the demo section. */
  format: "kubernetes" | "terraform" | "docker-compose";
  workload: WorkloadProfile;
}

import wellYaml from "../fixtures/deployment-well-provisioned.yaml?raw";
import moderateYaml from "../fixtures/deployment-moderate-overprovisioned.yaml?raw";
import heavyYaml from "../fixtures/deployment-heavy-overprovisioned.yaml?raw";
import tfWell from "../fixtures/main-well-provisioned.tf?raw";
import tfModerate from "../fixtures/main-moderate-overprovisioned.tf?raw";
import tfHeavy from "../fixtures/main-heavy-overprovisioned.tf?raw";
import composeWell from "../fixtures/compose-well-provisioned.yaml?raw";
import composeModerate from "../fixtures/compose-moderate-overprovisioned.yaml?raw";
import composeHeavy from "../fixtures/compose-heavy-overprovisioned.yaml?raw";

/** Kubernetes demo scenarios. */
export const KUBERNETES_PRESETS: DemoPreset[] = [
  {
    id: "well",
    label: "Well-provisioned",
    description: "2× 0.5c/512Mi — expect no recommendation",
    yaml: wellYaml,
    fileName: "well-deployment.yaml",
    format: "kubernetes",
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
    fileName: "moderate-deployment.yaml",
    format: "kubernetes",
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
    fileName: "heavy-deployment.yaml",
    format: "kubernetes",
    workload: {
      application_type: "e-commerce",
      expected_users: 10000,
      traffic_level: "medium",
      max_latency_ms: 150,
      availability_target: 99.9,
    },
  },
];

/** Terraform demo scenarios (Phase 12). */
export const TERRAFORM_PRESETS: DemoPreset[] = [
  {
    id: "tf-well",
    label: "Well-provisioned",
    description: "2× t3.medium (2 vCPU/4GiB) — expect few recommendations",
    yaml: tfWell,
    fileName: "main-well-provisioned.tf",
    format: "terraform",
    workload: {
      application_type: "rest-api",
      expected_users: 1000,
      traffic_level: "medium",
      max_latency_ms: 200,
      availability_target: 99.0,
    },
  },
  {
    id: "tf-moderate",
    label: "Moderate overprovisioned",
    description: "3× t3.large (2 vCPU/8GiB) — some scale-down expected",
    yaml: tfModerate,
    fileName: "main-moderate-overprovisioned.tf",
    format: "terraform",
    workload: {
      application_type: "web-application",
      expected_users: 10000,
      traffic_level: "medium",
      max_latency_ms: 150,
      availability_target: 99.9,
    },
  },
  {
    id: "tf-heavy",
    label: "Heavy overprovisioned",
    description: "8× m5.2xlarge (8 vCPU/32GiB) — expect big savings",
    yaml: tfHeavy,
    fileName: "main-heavy-overprovisioned.tf",
    format: "terraform",
    workload: {
      application_type: "e-commerce",
      expected_users: 10000,
      traffic_level: "medium",
      max_latency_ms: 150,
      availability_target: 99.9,
    },
  },
];

/** Docker Compose demo scenarios (Phase 13). */
export const COMPOSE_PRESETS: DemoPreset[] = [
  {
    id: "compose-well",
    label: "Well-provisioned",
    description: "2× 0.5c/512M — expect few recommendations",
    yaml: composeWell,
    fileName: "compose-well-provisioned.yaml",
    format: "docker-compose",
    workload: {
      application_type: "rest-api",
      expected_users: 1000,
      traffic_level: "medium",
      max_latency_ms: 200,
      availability_target: 99.0,
    },
  },
  {
    id: "compose-moderate",
    label: "Moderate overprovisioned",
    description: "4× 2c/4G — some scale-down expected",
    yaml: composeModerate,
    fileName: "compose-moderate-overprovisioned.yaml",
    format: "docker-compose",
    workload: {
      application_type: "web-application",
      expected_users: 10000,
      traffic_level: "medium",
      max_latency_ms: 150,
      availability_target: 99.9,
    },
  },
  {
    id: "compose-heavy",
    label: "Heavy overprovisioned",
    description: "8× 8c/16G + sidecar — expect big savings",
    yaml: composeHeavy,
    fileName: "compose-heavy-overprovisioned.yaml",
    format: "docker-compose",
    workload: {
      application_type: "e-commerce",
      expected_users: 10000,
      traffic_level: "medium",
      max_latency_ms: 150,
      availability_target: 99.9,
    },
  },
];

/** Flat lookup kept for tests/debug tooling. */
export const DEMO_PRESETS: DemoPreset[] = [
  ...KUBERNETES_PRESETS,
  ...TERRAFORM_PRESETS,
  ...COMPOSE_PRESETS,
];
