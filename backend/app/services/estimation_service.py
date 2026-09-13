"""Transparent prototype estimates for cost, energy use, and carbon impact."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.schemas.unified_schema import (
    EstimationAssumptions,
    FeatureVector,
    SustainabilityEstimation,
    UtilizationPrediction,
)

DISCLAIMER = (
    "Prototype estimate based on configurable allocation, utilization, power, PUE, "
    "pricing, and carbon-intensity assumptions; it is not measured usage, a cloud bill, "
    "or exact real-world emissions."
)


@dataclass(frozen=True)
class EstimationParameters:
    period_hours: float
    cpu_cost_per_vcpu_hour_usd: float
    memory_cost_per_gb_hour_usd: float
    cpu_power_watts_per_active_vcpu: float
    memory_power_watts_per_active_gb: float
    data_center_pue: float
    carbon_intensity_gco2_per_kwh: float

    def __post_init__(self) -> None:
        if self.period_hours <= 0:
            raise ValueError("period_hours must be greater than zero")
        if self.data_center_pue < 1:
            raise ValueError("data_center_pue must be at least one")
        non_negative = (
            self.cpu_cost_per_vcpu_hour_usd,
            self.memory_cost_per_gb_hour_usd,
            self.cpu_power_watts_per_active_vcpu,
            self.memory_power_watts_per_active_gb,
            self.carbon_intensity_gco2_per_kwh,
        )
        if any(value < 0 for value in non_negative):
            raise ValueError("estimation costs, power values, and carbon intensity must be non-negative")


def parameters_from_settings(settings: Settings | None = None) -> EstimationParameters:
    """Extract the estimation settings once into a small testable value object."""
    values = settings or get_settings()
    return EstimationParameters(
        period_hours=values.estimation_period_hours,
        cpu_cost_per_vcpu_hour_usd=values.cpu_cost_per_vcpu_hour_usd,
        memory_cost_per_gb_hour_usd=values.memory_cost_per_gb_hour_usd,
        cpu_power_watts_per_active_vcpu=values.cpu_power_watts_per_active_vcpu,
        memory_power_watts_per_active_gb=values.memory_power_watts_per_active_gb,
        data_center_pue=values.data_center_pue,
        carbon_intensity_gco2_per_kwh=values.carbon_intensity_gco2_per_kwh,
    )


def estimate_sustainability(
    features: FeatureVector,
    prediction: UtilizationPrediction,
    parameters: EstimationParameters | None = None,
) -> SustainabilityEstimation:
    """Estimate one analysis period from provisioned resources and predicted utilization.

    Cost is allocation-based because cloud resources are usually billed while provisioned.
    Energy is utilization-based, then multiplied by PUE for data-center overhead.
    """
    values = parameters or parameters_from_settings()
    total_cpu = max(features.total_cpu_capacity, 0.0)
    total_memory = max(features.total_memory_capacity, 0.0)
    active_cpu = total_cpu * prediction.cpu_utilization
    active_memory = total_memory * prediction.memory_utilization

    estimated_cost = values.period_hours * (
        total_cpu * values.cpu_cost_per_vcpu_hour_usd
        + total_memory * values.memory_cost_per_gb_hour_usd
    )
    it_power_watts = (
        active_cpu * values.cpu_power_watts_per_active_vcpu
        + active_memory * values.memory_power_watts_per_active_gb
    )
    estimated_energy_kwh = (
        it_power_watts * values.period_hours * values.data_center_pue / 1000
    )
    estimated_carbon_kg = (
        estimated_energy_kwh * values.carbon_intensity_gco2_per_kwh / 1000
    )

    return SustainabilityEstimation(
        estimated_cost_usd=estimated_cost,
        estimated_energy_kwh=estimated_energy_kwh,
        estimated_carbon_kg_co2e=estimated_carbon_kg,
        active_cpu_vcpus=active_cpu,
        active_memory_gb=active_memory,
        assumptions=EstimationAssumptions(
            period_hours=values.period_hours,
            cpu_cost_per_vcpu_hour_usd=values.cpu_cost_per_vcpu_hour_usd,
            memory_cost_per_gb_hour_usd=values.memory_cost_per_gb_hour_usd,
            cpu_power_watts_per_active_vcpu=values.cpu_power_watts_per_active_vcpu,
            memory_power_watts_per_active_gb=values.memory_power_watts_per_active_gb,
            data_center_pue=values.data_center_pue,
            carbon_intensity_gco2_per_kwh=values.carbon_intensity_gco2_per_kwh,
        ),
        disclaimer=DISCLAIMER,
    )
