/**
 * TypeScript mirrors of the backend Pydantic response schemas
 * (backend/app/schemas/*), verified against live API responses.
 */

export interface ConstraintCheck {
  name: string;
  status: "pass" | "fail";
  required: string;
  actual: string;
  explanation: string;
}

export interface ConstraintEvaluation {
  satisfied: boolean;
  checks: ConstraintCheck[];
  disclaimer: string;
}

export interface EstimationAssumptions {
  period_hours: number;
  cpu_cost_per_vcpu_hour_usd: number;
  memory_cost_per_gb_hour_usd: number;
  cpu_power_watts_per_active_vcpu: number;
  memory_power_watts_per_active_gb: number;
  data_center_pue: number;
  carbon_intensity_gco2_per_kwh: number;
}

export interface SustainabilityEstimation {
  estimated_cost_usd: number;
  estimated_energy_kwh: number;
  estimated_carbon_kg_co2e: number;
  active_cpu_vcpus: number;
  active_memory_gb: number;
  assumptions: EstimationAssumptions;
  disclaimer: string;
}

export interface UtilizationPrediction {
  cpu_utilization: number;
  memory_utilization: number;
  model_type: string;
  model_created_at: string | null;
}

export interface InfrastructureConfiguration {
  source_type: string;
  application: string;
  namespace: string;
  replicas: number;
  cpu_request: number | null;
  cpu_limit: number | null;
  memory_request_gb: number | null;
  memory_limit_gb: number | null;
  autoscaling_enabled: boolean;
  container_image: string | null;
  // Terraform-specific fields (Phase 12); null for Kubernetes sources.
  cloud_provider: string | null;
  region: string | null;
  instance_type: string | null;
  instance_count: number | null;
  storage_gb: number | null;
  parser_warnings: string[] | null;
}

export interface WorkloadProfile {
  application_type: string;
  expected_users: number;
  traffic_level: string;
  max_latency_ms: number;
  availability_target: number;
  average_rps?: number | null;
  peak_rps?: number | null;
  traffic_pattern?: string | null;
  storage_gb?: number | null;
  autoscaling_required?: boolean | null;
  performance_priority?: string;
  cost_priority?: string;
  sustainability_priority?: string;
}

export interface FeatureVector {
  application_type: string;
  application_type_code: number;
  expected_users: number;
  traffic_level: string;
  traffic_score: number;
  max_latency_ms: number;
  availability_target: number;
  cpu: number;
  memory_gb: number;
  replicas: number;
  storage_gb: number | null;
  autoscaling_enabled: boolean;
  autoscaling_enabled_int: number;
  source_type: string;
  total_cpu_capacity: number;
  total_memory_capacity: number;
  users_per_replica: number;
}

export interface AnalyzeResponse {
  analysis_id: string;
  configuration: InfrastructureConfiguration;
  workload: WorkloadProfile;
  features: FeatureVector;
  prediction: UtilizationPrediction;
  estimation: SustainabilityEstimation;
  constraints: ConstraintEvaluation;
}

export interface ScoreComponent {
  name: string;
  raw_value: string;
  score: number;
  weight: number;
  explanation: string;
}

export interface SustainabilityScore {
  score: number;
  grade: string;
  components: ScoreComponent[];
  methodology: string;
  disclaimer: string;
}

export interface AnalysisScoreResponse {
  analysis_id: string;
  score: SustainabilityScore;
}

export interface OptimizationScores {
  baseline: SustainabilityScore;
  optimized: SustainabilityScore | null;
  improvement: number | null;
}

export interface RecommendationItem {
  parameter: string;
  current_value: string;
  suggested_value: string;
  reason: string;
}

export interface RejectedCandidate {
  summary: string;
  reason: string;
}

export interface EstimationTotals {
  estimated_cost_usd: number;
  estimated_energy_kwh: number;
  estimated_carbon_kg_co2e: number;
}

export interface RecommendationTotals {
  baseline: EstimationTotals;
  optimized: EstimationTotals;
  cost_reduction_usd: number;
  energy_reduction_kwh: number;
  carbon_reduction_kg_co2e: number;
}

export interface RecommendationSet {
  status: "recommended" | "no_recommendation";
  baseline_configuration: Record<string, unknown>;
  optimized_configuration: Record<string, unknown> | null;
  totals: RecommendationTotals | null;
  items: RecommendationItem[];
  rejected_candidates: RejectedCandidate[];
  explanation: string;
  disclaimer: string;
}

export interface OptimizeResponse {
  analysis_id: string;
  recommendation_set: RecommendationSet;
  scores: OptimizationScores;
}

export interface ConfigChange {
  parameter: string;
  current: string;
  suggested: string;
}

export interface OptimizedConfigResponse {
  analysis_id: string;
  source: string;
  original_yaml: string;
  optimized_yaml: string;
  diff: string[];
  changes: ConfigChange[];
  /** Per-target adaptation notices (Terraform/Compose paths, Phase 18). */
  notes: string[];
  disclaimer: string;
}

export interface ValidationResponse {
  valid: boolean;
  errors: string[];
}

// ---- Mode B generation (Phases 15-17) ----

export type GenerationTarget =
  | "kubernetes"
  | "terraform"
  | "docker_compose"
  | "terraform+kubernetes";

export interface ResourceRequirements {
  cpu_cores: number;
  memory_gb: number;
  replica_estimate: number;
  replica_minimum: number;
  storage_gb: number | null;
  autoscaling_required: boolean;
  peak_factor: number;
  notes: string[];
}

export interface TargetSelection {
  target: GenerationTarget;
  source: "user" | "auto";
  explanation: string;
}

export interface GeneratedArtifact {
  target: GenerationTarget;
  filename: string;
  content: string;
  round_trip_valid: boolean;
  notes: string[];
}

export interface GenerationEvaluation {
  status: "recommended" | "infeasible";
  requirements: ResourceRequirements;
  candidates: Array<{
    plan: {
      variant: string;
      summary: string;
      configuration: InfrastructureConfiguration;
    };
    prediction: UtilizationPrediction;
    estimation: SustainabilityEstimation;
    constraints: ConstraintEvaluation;
    score: SustainabilityScore;
    eligible: boolean;
    rejection_reasons: string[];
  }>;
  selected_index: number | null;
  weights_used: Record<string, number>;
  ranking_explanation: string;
  infeasibility_explanation: string | null;
  disclaimer: string;
}

export interface GenerateResponse {
  generation_id: string;
  status: string;
  selected_configuration: InfrastructureConfiguration | null;
  target_selection: TargetSelection;
  requirements: ResourceRequirements;
  artifacts: GeneratedArtifact[];
  evaluation: GenerationEvaluation;
}

export interface GenerationInfeasibleError {
  generation_id: string;
  error: "infeasible";
  explanation: string;
}
