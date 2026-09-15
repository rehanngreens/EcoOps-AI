"""Phase 12 Terraform parser: AWS EC2-centric HCL subset -> normalized features.

Converts a Terraform configuration into the same normalized representation
the Phase 2 Kubernetes parser produces, so the downstream ML prediction,
estimation, constraint, and scoring pipeline is source-agnostic (design doc
section 8). The parser deliberately implements a DOCUMENTED SUBSET:

- ``provider "aws"`` block -> region
- ``resource "aws_instance"`` blocks -> instance_type (via the
  ``aws_instance_metadata`` table), count (default 1), tags.Name (preferred
  application name), root_block_device / aws_ebs_volume -> storage_gb
- ``resource "aws_autoscaling_group"`` presence -> autoscaling_enabled = true
  (detection only; ASG-driven sizing is out of scope)

Explicitly unsupported (rejected with a clear error, never guessed):
variable/locals interpolation (``${...}``), multiple aws_instance blocks,
and any other resource types (aws_launch_template, aws_ecs_*, etc.).

HCL is parsed with anchored regular expressions over block structure rather
than a full grammar. This is a documented trade-off: no new dependency,
fully deterministic, and easy to test. Strings in single-line ``key = value``
form are supported; heredocs and multi-line expressions are not.
"""

from __future__ import annotations

import re
from typing import Any

from app.parsers.aws_instance_metadata import get_instance_type

_PROVIDER_BLOCK = re.compile(r'^\s*provider\s+"aws"\s*\{', re.MULTILINE)
_RESOURCE_BLOCK = re.compile(
    r'^\s*resource\s+"([a-zA-Z0-9_]+)"\s+"([a-zA-Z0-9_\-]+)"\s*\{',
    re.MULTILINE,
)
_INTERPOLATION = re.compile(r"\$\{")
_QUOTED_STRING = re.compile(r'"((?:[^"\\]|\\.)*)"')
_HCL_COMMENT = re.compile(r"#.*$|//.*$", re.MULTILINE)
_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


class TerraformParserError(ValueError):
    """Raised when a Terraform configuration cannot be parsed into normalized features."""


def parse_terraform(tf_text: str) -> dict[str, Any]:
    """Parse Terraform text for an aws_instance setup and return normalized features."""
    cleaned = _strip_comments(tf_text)
    if not cleaned.strip():
        raise TerraformParserError("Terraform content is empty")

    if _INTERPOLATION.search(cleaned):
        raise TerraformParserError(
            "Variable interpolation (${...}) is not supported by the "
            "Terraform parser; provide literal values"
        )

    blocks = _find_resource_blocks(cleaned)
    instances = [b for b in blocks if b.resource_type == "aws_instance"]
    unsupported = sorted(
        {b.resource_type for b in blocks if b.resource_type != "aws_instance"}
    )

    if not instances:
        if unsupported:
            raise TerraformParserError(
                f"Unsupported Terraform resource type(s): {', '.join(unsupported)}. "
                "Only 'aws_instance' is supported by the MVP parser."
            )
        raise TerraformParserError(
            "No resource blocks found in Terraform configuration"
        )
    if len(instances) > 1:
        names = ", ".join(f'aws_instance."{b.label}"' for b in instances)
        raise TerraformParserError(
            f"Multiple aws_instance blocks are not supported: {names}. "
            "Provide exactly one aws_instance resource."
        )

    return _parse_instance_block(cleaned, instances[0], blocks)


def validate_terraform(tf_text: str) -> list[str]:
    """Return a list of validation errors; empty list means the configuration is valid."""
    try:
        parse_terraform(tf_text)
    except TerraformParserError as exc:
        return [str(exc)]
    return []


def _strip_comments(tf_text: str) -> str:
    without_block = _BLOCK_COMMENT.sub("", tf_text)
    return _HCL_COMMENT.sub("", without_block)


def _find_resource_blocks(cleaned: str) -> list["_ResourceBlock"]:
    blocks: list[_ResourceBlock] = []
    for match in _RESOURCE_BLOCK.finditer(cleaned):
        blocks.append(
            _ResourceBlock(
                resource_type=match.group(1),
                label=match.group(2),
                start=match.end(),
            )
        )
    return blocks


class _ResourceBlock:
    __slots__ = ("resource_type", "label", "start")

    def __init__(self, resource_type: str, label: str, start: int) -> None:
        self.resource_type = resource_type
        self.label = label
        self.start = start


def _block_body(cleaned: str, start: int) -> str:
    """Return the body of the block that opens at ``start`` (after the '{')."""
    depth = 1
    in_string = False
    i = start
    while i < len(cleaned):
        char = cleaned[i]
        if in_string:
            if char == "\\":
                i += 2
                continue
            if char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start:i]
        i += 1
    raise TerraformParserError(
        "Unbalanced braces in Terraform configuration; check the block structure"
    )


def _parse_instance_block(
    cleaned: str,
    instance: _ResourceBlock,
    blocks: list[_ResourceBlock],
) -> dict[str, Any]:
    body = _block_body(cleaned, instance.start)

    instance_type_raw = _get_raw(body, "instance_type")
    if instance_type_raw is None:
        raise TerraformParserError(
            "aws_instance block must define an 'instance_type'"
        )
    instance_type = _get_string(body, "instance_type")
    if instance_type is None:
        raise TerraformParserError(
            f"aws_instance 'instance_type' must be a quoted string literal "
            f"(got {instance_type_raw!r}); variables and references are not "
            "supported by this parser"
        )

    spec = get_instance_type(instance_type)
    if spec is None:
        raise TerraformParserError(
            f"Unknown EC2 instance type '{instance_type}': it is not in the "
            "instance metadata table and no base family could resolve it."
        )
    instance_spec, metadata_warning = spec

    count = _get_int(body, "count", default=1)
    if count is None:
        # A literal count that is not a plain number (e.g. a local ref) will
        # fail _get_int and we surface it instead of guessing.
        raise TerraformParserError(
            f"aws_instance 'count' must be a plain integer for this parser "
            f"(got {_get_raw(body, 'count')!r})"
        )
    if count < 1:
        raise TerraformParserError(
            f"aws_instance 'count' must be >= 1 (got {count})"
        )

    name = _get_string(_get_map(body, "tags"), "Name") or instance.label

    storage_gb = _extract_storage_gb(body)

    region = None
    provider_positions = [
        match.end() for match in _PROVIDER_BLOCK.finditer(cleaned)
    ]
    if provider_positions:
        provider_body = _block_body(cleaned, provider_positions[0])
        region = _get_string(provider_body, "region")

    autoscaling_enabled = any(b.resource_type == "aws_autoscaling_group" for b in blocks)

    result: dict[str, Any] = {
        "source_type": "terraform",
        "application": name,
        "namespace": "default",
        "replicas": count,
        "cpu_request": float(instance_spec.vcpu),
        "cpu_limit": None,
        "memory_request_gb": float(instance_spec.memory_gib),
        "memory_limit_gb": None,
        "autoscaling_enabled": autoscaling_enabled,
        "container_image": None,
    }

    # Terraform-specific extras (additive schema fields; the K8s parser does
    # not emit these, and downstream services treat them as pass-through).
    result["cloud_provider"] = "aws"
    if region:
        result["region"] = region
    result["instance_type"] = instance_type
    result["instance_count"] = count
    result["storage_gb"] = storage_gb

    if metadata_warning:
        result["parser_warnings"] = [metadata_warning]

    return result


def _extract_storage_gb(body: str) -> float | None:
    """Best-effort storage extraction from root_block_device or ebs volumes."""
    size_gb: float | None = None

    root_match = re.search(r"root_block_device\s*\{", body)
    if root_match:
        root_body = _block_body(body, root_match.end())
        size_gb = _get_float(root_body, "volume_size")

    if size_gb is None:
        ebs_match = re.search(r"\bebs_block_device\s*\{", body)
        if ebs_match:
            ebs_body = _block_body(body, ebs_match.end())
            size_gb = _get_float(ebs_body, "volume_size")

    return size_gb


def _get_raw(body: str, key: str) -> str | None:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*(.+?)\s*$", body, re.MULTILINE)
    return match.group(1) if match else None


def _get_string(body: str, key: str) -> str | None:
    raw = _get_raw(body, key)
    if raw is None:
        return None
    quoted = _QUOTED_STRING.match(raw)
    return quoted.group(1) if quoted else None


def _get_int(body: str, key: str, default: int | None = None) -> int | None:
    raw = _get_raw(body, key)
    if raw is None:
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return None


def _get_float(body: str, key: str) -> float | None:
    raw = _get_raw(body, key)
    if raw is None:
        return None
    try:
        return float(raw.strip())
    except ValueError:
        return None


def _get_map(body: str, key: str) -> str:
    match = re.search(rf"^\s*{re.escape(key)}\s*=\s*\{{", body, re.MULTILINE)
    if match is None:
        return ""
    return _block_body(body, match.end())
