"""AWS EC2 instance-type metadata for the Terraform parser (Phase 12).

The Terraform parser needs vCPU and memory for each ``instance_type`` so the
normalized configuration matches the schema the ML/estimation pipeline
already consumes. This module is the single structured source for that
metadata (design doc section 9: keep infrastructure metadata out of random
source files).

Scope notes:

- Only the vCPU count and memory size are provided here. Pricing stays in
  the configurable settings (design doc section 17: keep provider pricing
  configurable and separate from business logic).
- The table intentionally covers a pragmatic subset of common families.
  Unknown sizes in a KNOWN family fall back to the base family's specs with
  a warning (for example ``m5a.2xlarge`` -> ``m5.2xlarge``); the warning is
  surfaced in the parsed configuration so the guess is never silent.
- Sizes are the documented AWS specifications; burstable t3/t3a values are
  the baseline (non-burst) specs.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstanceSpec:
    vcpu: int
    memory_gib: int


# family -> size -> spec. Sizes follow the AWS naming scheme
# (micro, small, medium, large, xlarge, N+xlarge).
_INSTANCE_TABLE: dict[str, dict[str, InstanceSpec]] = {
    "t3": {
        "micro": InstanceSpec(2, 1),
        "small": InstanceSpec(2, 2),
        "medium": InstanceSpec(2, 4),
        "large": InstanceSpec(2, 8),
        "xlarge": InstanceSpec(4, 16),
        "2xlarge": InstanceSpec(8, 32),
    },
    "t3a": {
        "micro": InstanceSpec(2, 1),
        "small": InstanceSpec(2, 2),
        "medium": InstanceSpec(2, 4),
        "large": InstanceSpec(2, 8),
        "xlarge": InstanceSpec(4, 16),
        "2xlarge": InstanceSpec(8, 32),
    },
    "m5": {
        "large": InstanceSpec(2, 8),
        "xlarge": InstanceSpec(4, 16),
        "2xlarge": InstanceSpec(8, 32),
        "4xlarge": InstanceSpec(16, 64),
        "8xlarge": InstanceSpec(32, 128),
        "12xlarge": InstanceSpec(48, 192),
        "16xlarge": InstanceSpec(64, 256),
    },
    "m6i": {
        "large": InstanceSpec(2, 8),
        "xlarge": InstanceSpec(4, 16),
        "2xlarge": InstanceSpec(8, 32),
        "4xlarge": InstanceSpec(16, 64),
        "8xlarge": InstanceSpec(32, 128),
        "12xlarge": InstanceSpec(48, 192),
        "16xlarge": InstanceSpec(64, 256),
    },
    "c5": {
        "large": InstanceSpec(2, 4),
        "xlarge": InstanceSpec(4, 8),
        "2xlarge": InstanceSpec(8, 16),
        "4xlarge": InstanceSpec(16, 32),
        "9xlarge": InstanceSpec(36, 72),
    },
    "c6i": {
        "large": InstanceSpec(2, 4),
        "xlarge": InstanceSpec(4, 8),
        "2xlarge": InstanceSpec(8, 16),
        "4xlarge": InstanceSpec(16, 32),
        "8xlarge": InstanceSpec(32, 64),
    },
    "r5": {
        "large": InstanceSpec(2, 16),
        "xlarge": InstanceSpec(4, 32),
        "2xlarge": InstanceSpec(8, 64),
        "4xlarge": InstanceSpec(16, 128),
        "8xlarge": InstanceSpec(32, 256),
    },
    "r6i": {
        "large": InstanceSpec(2, 16),
        "xlarge": InstanceSpec(4, 32),
        "2xlarge": InstanceSpec(8, 64),
        "4xlarge": InstanceSpec(16, 128),
        "8xlarge": InstanceSpec(32, 256),
    },
}


def get_instance_type(name: str) -> tuple[InstanceSpec, str | None] | None:
    """Resolve an instance type to its spec.

    Returns ``(spec, warning)`` where ``warning`` is ``None`` for an exact
    match and a human-readable note when a base-family fallback was used.
    Returns ``None`` when the type is unknown and cannot be resolved.
    """
    normalized = name.strip().lower()
    family, _, size = normalized.partition(".")
    if not size:
        return None

    family_table = _INSTANCE_TABLE.get(family)
    if family_table is not None and size in family_table:
        return family_table[size], None

    # Family fallback: strip trailing letters one at a time
    # (m5a -> m5, r5b -> r5, c6id -> c6i). Bounded loop.
    candidate = family
    while candidate and candidate not in _INSTANCE_TABLE:
        if not candidate[-1].isalpha():
            return None
        candidate = candidate[:-1]
    if not candidate:
        return None

    fallback_table = _INSTANCE_TABLE[candidate]
    if size not in fallback_table:
        return None
    warning = (
        f"Instance type '{name}' is not in the metadata table; "
        f"specifications were resolved from the base family "
        f"'{candidate}.{size}' and may differ (for example in processor "
        f"generation or clock speed)."
    )
    return fallback_table[size], warning
