"""Phase 16 target selection — "Let EcoOps AI choose" (design doc 44.4).

Explicit, ordered rules evaluated against the normalized requirements. The
FIRST matching rule wins, and the matched rule is reported in the
explanation. No ML, no LLM, no magic. Explicitly selected targets skip
this module entirely (the caller passes source="user").

Rule source: design doc section 44.4, verbatim ordering:

1. batch processing -> Docker Compose (scheduled, non-latency-critical
   work does not need an orchestrator).
2. database -> Terraform + Kubernetes; without a storage requirement,
   Terraform alone (managed database).
3. autoscaling required AND (bursty OR e-commerce/streaming) -> Kubernetes
   (HPA is the designed mechanism).
4. machine-learning / ai-inference -> Kubernetes (GPU scheduling semantics).
5. autoscaling required -> Kubernetes.
6. expected users >= 100,000 OR availability >= 99.9% -> Terraform + Kubernetes.
7. otherwise (simple small services) -> Docker Compose.
"""

from __future__ import annotations

from app.schemas.generation_schema import TargetSelection
from app.schemas.workload_schema import WorkloadProfile

# Rule 3's application types (burst-elasticity by design).
_ELASTIC_TYPES = {"e-commerce", "streaming"}

# Rule 4's types (GPU scheduling semantics).
_GPU_TYPES = {"machine-learning", "ai-inference"}

_AUTO_USERS_THRESHOLD = 100_000
_AUTO_AVAILABILITY_THRESHOLD = 99.9


def select_target_auto(workload: WorkloadProfile) -> TargetSelection:
    """First-match-wins rule evaluation (section 44.4). Deterministic."""
    app = workload.application_type
    autoscaling = bool(workload.autoscaling_required)
    pattern = workload.traffic_pattern
    storage = workload.storage_gb
    users = workload.expected_users
    availability = workload.availability_target

    if app == "batch":
        return TargetSelection(
            target="docker_compose",
            source="auto",
            explanation=(
                "Rule 1: batch processing is scheduled, non-latency-critical "
                "work, so it does not need an orchestrator — Docker Compose."
            ),
        )

    if app == "database":
        if storage is None or storage <= 0:
            return TargetSelection(
                target="terraform",
                source="auto",
                explanation=(
                    "Rule 2: a database without a stated storage requirement "
                    "maps to a managed-database pattern — Terraform alone."
                ),
            )
        return TargetSelection(
            target="terraform+kubernetes",
            source="auto",
            explanation=(
                "Rule 2: the data tier uses Terraform-provisioned storage "
                "with Kubernetes running the workload — Terraform + Kubernetes."
            ),
        )

    if autoscaling and (pattern == "bursty" or app in _ELASTIC_TYPES):
        return TargetSelection(
            target="kubernetes",
            source="auto",
            explanation=(
                "Rule 3: autoscaling with bursty or e-commerce/streaming "
                "traffic uses the Kubernetes HPA as the designed mechanism."
            ),
        )

    if app in _GPU_TYPES:
        return TargetSelection(
            target="kubernetes",
            source="auto",
            explanation=(
                "Rule 4: machine-learning / AI-inference workloads map to "
                "Kubernetes for GPU scheduling semantics."
            ),
        )

    if autoscaling:
        return TargetSelection(
            target="kubernetes",
            source="auto",
            explanation=(
                "Rule 5: autoscaling is required, and Kubernetes is the "
                "target with HPA semantics."
            ),
        )

    if users >= _AUTO_USERS_THRESHOLD or availability >= _AUTO_AVAILABILITY_THRESHOLD:
        if users >= _AUTO_USERS_THRESHOLD:
            reason = (
                f"Rule 6: {users:g} expected users calls for "
                f"Terraform-provisioned infrastructure plus Kubernetes "
                f"workloads."
            )
        else:
            reason = (
                f"Rule 6: a {availability:g}% availability target calls "
                f"for Terraform-provisioned infrastructure plus Kubernetes "
                f"workloads."
            )
        return TargetSelection(target="terraform+kubernetes", source="auto", explanation=reason)

    return TargetSelection(
        target="docker_compose",
        source="auto",
        explanation=(
            "Rule 7: a simple small service without special requirements — "
            "Docker Compose."
        ),
    )


def select_target(
    requested: str | None,
    workload: WorkloadProfile,
) -> TargetSelection:
    """Resolve the generation target: explicit choice wins, else the rules."""
    if requested and requested != "auto":
        normalized = requested.strip().lower().replace(" ", "")
        aliases = {
            "terraform+kubernetes": "terraform+kubernetes",
            "terraform_kubernetes": "terraform+kubernetes",
        }
        target = aliases.get(normalized, normalized)
        valid = {"kubernetes", "terraform", "docker_compose", "terraform+kubernetes"}
        if target not in valid:
            raise ValueError(
                f"Unknown generation target '{requested}'; expected one of "
                f"{sorted(valid)} or 'auto'"
            )
        return TargetSelection(
            target=target,
            source="user",
            explanation="Target selected explicitly by the user.",
        )
    return select_target_auto(workload)
