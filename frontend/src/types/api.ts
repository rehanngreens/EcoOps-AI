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
  disclaimer: string;
}

export interface ValidationResponse {
  valid: boolean;
  errors: string[];
}
