import type {
  AnalyzeResponse,
  OptimizedConfigResponse,
  OptimizeResponse,
} from "../types/api";

export const analyzeResponse: AnalyzeResponse = {
  analysis_id: "test-analysis-1",
  configuration: {
    source_type: "kubernetes",
    application: "api-backend",
    namespace: "ecommerce",
    replicas: 8,
    cpu_request: 8,
    cpu_limit: 8,
    memory_request_gb: 16,
    memory_limit_gb: 16,
    autoscaling_enabled: false,
    container_image: "ecommerce/api-backend:1.0.0",
  },
  workload: {
    application_type: "e-commerce",
    expected_users: 10000,
    traffic_level: "medium",
    max_latency_ms: 150,
    availability_target: 99.9,
  },
  features: {
    application_type: "e-commerce",
    application_type_code: 1,
    expected_users: 10000,
    traffic_level: "medium",
    traffic_score: 2,
    max_latency_ms: 150,
    availability_target: 99.9,
    cpu: 8,
    memory_gb: 16,
    replicas: 8,
    storage_gb: null,
    autoscaling_enabled: false,
    autoscaling_enabled_int: 0,
    source_type: "kubernetes",
    total_cpu_capacity: 64,
    total_memory_capacity: 128,
    users_per_replica: 1250,
  },
  prediction: {
    cpu_utilization: 0.167,
    memory_utilization: 0.195,
    model_type: "RandomForestRegressor",
    model_created_at: null,
  },
  estimation: {
    estimated_cost_usd: 2336.0,
    estimated_energy_kwh: 176.63,
    estimated_carbon_kg_co2e: 75.95,
    active_cpu_vcpus: 10.69,
    active_memory_gb: 24.96,
    assumptions: {
      period_hours: 730,
      cpu_cost_per_vcpu_hour_usd: 0.04,
      memory_cost_per_gb_hour_usd: 0.005,
      cpu_power_watts_per_active_vcpu: 15,
      memory_power_watts_per_active_gb: 0.5,
      data_center_pue: 1.4,
      carbon_intensity_gco2_per_kwh: 430,
    },
    disclaimer: "Prototype estimate based on configurable assumptions.",
  },
  constraints: {
    satisfied: false,
    checks: [
      {
        name: "cpu_headroom",
        status: "pass",
        required: "cpu utilization <= 70%",
        actual: "16.7%",
        explanation: "ok",
      },
      {
        name: "memory_headroom",
        status: "pass",
        required: "memory utilization <= 85%",
        actual: "19.5%",
        explanation: "ok",
      },
      {
        name: "latency_feasibility",
        status: "pass",
        required: "<= 150ms",
        actual: "~90ms",
        explanation: "ok",
      },
      {
        name: "availability_replicas",
        status: "pass",
        required: ">= 3 replicas",
        actual: "8",
        explanation: "ok",
      },
      {
        name: "user_capacity",
        status: "fail",
        required: "capacity >= 10000 users",
        actual: "8000",
        explanation: "Replica capacity below the expected user count.",
      },
    ],
    disclaimer: "Prototype heuristics.",
  },
};

const score = {
  score: 0.2004,
  grade: "F",
  components: [
    {
      name: "resource_efficiency",
      raw_value: "predicted cpu utilization 16.7%",
      score: 0.167,
      weight: 0.3,
      explanation: "e",
    },
    {
      name: "energy_efficiency",
      raw_value: "176.63 kWh/period",
      score: 0.169,
      weight: 0.25,
      explanation: "e",
    },
    {
      name: "carbon_impact",
      raw_value: "75.95 kgCO2e/period",
      score: 0.169,
      weight: 0.25,
      explanation: "e",
    },
    {
      name: "cost_efficiency",
      raw_value: "$2336.00/period",
      score: 0.173,
      weight: 0.15,
      explanation: "e",
    },
    {
      name: "constraint_compliance",
      raw_value: "4/5 checks passed",
      score: 0.8,
      weight: 0.05,
      explanation: "e",
    },
  ],
  methodology: "Weighted mean of five normalized components.",
  disclaimer: "Prototype heuristic score.",
};

export const optimizeRecommended: OptimizeResponse = {
  analysis_id: "test-analysis-1",
  recommendation_set: {
    status: "recommended",
    baseline_configuration: { replicas: 8 },
    optimized_configuration: { replicas: 4 },
    totals: {
      baseline: {
        estimated_cost_usd: 2336.0,
        estimated_energy_kwh: 176.63,
        estimated_carbon_kg_co2e: 75.95,
      },
      optimized: {
        estimated_cost_usd: 934.4,
        estimated_energy_kwh: 70.65,
        estimated_carbon_kg_co2e: 30.38,
      },
      cost_reduction_usd: 1401.6,
      energy_reduction_kwh: 105.98,
      carbon_reduction_kg_co2e: 45.57,
    },
    items: [
      {
        parameter: "cpu_request",
        current_value: "8 cores",
        suggested_value: "2 cores",
        reason: "Estimated savings with all constraints satisfied.",
      },
    ],
    rejected_candidates: [
      { summary: "8x 2c/16Gi (fixed)", reason: "failed constraint check(s): cpu_headroom" },
    ],
    explanation: "Selected candidate with all constraints satisfied.",
    disclaimer: "Recommendations are advisory prototype estimates.",
  },
  scores: {
    baseline: score,
    optimized: { ...score, score: 0.3795, grade: "F" },
    improvement: 0.1791,
  },
};

export const optimizeNone: OptimizeResponse = {
  analysis_id: "test-analysis-1",
  recommendation_set: {
    status: "no_recommendation",
    baseline_configuration: { replicas: 2 },
    optimized_configuration: null,
    totals: null,
    items: [],
    rejected_candidates: [
      { summary: "2x 0.25c/256Mi (fixed)", reason: "failed constraint check(s): cpu_headroom" },
    ],
    explanation: "No scale-down candidate satisfied all constraints; the current configuration is kept.",
    disclaimer: "Recommendations are advisory prototype estimates.",
  },
  scores: { baseline: score, optimized: null, improvement: null },
};

export const optimizedConfig: OptimizedConfigResponse = {
  analysis_id: "test-analysis-1",
  source: "stored_original",
  original_yaml: "apiVersion: apps/v1\nkind: Deployment",
  optimized_yaml: "apiVersion: apps/v1\nkind: Deployment\n# optimized",
  diff: [
    " apiVersion: apps/v1",
    " kind: Deployment",
    "-      replicas: 8",
    "+      replicas: 4",
  ],
  changes: [{ parameter: "replicas", current: "8", suggested: "4" }],
  disclaimer: "The optimized manifest is a proposal. Review the diff before deploying.",
};
