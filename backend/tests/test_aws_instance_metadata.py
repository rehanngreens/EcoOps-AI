"""Tests for the AWS instance-type metadata table (Phase 12)."""

from app.parsers.aws_instance_metadata import get_instance_type


def test_exact_matches() -> None:
    spec, warning = get_instance_type("t3.medium")
    assert (spec.vcpu, spec.memory_gib) == (2, 4)
    assert warning is None

    spec, warning = get_instance_type("m5.2xlarge")
    assert (spec.vcpu, spec.memory_gib) == (8, 32)
    assert warning is None

    spec, warning = get_instance_type("r5.4xlarge")
    assert (spec.vcpu, spec.memory_gib) == (16, 128)
    assert warning is None


def test_case_insensitive_and_whitespace_tolerant() -> None:
    spec, warning = get_instance_type("  M5.XLarge ")
    assert (spec.vcpu, spec.memory_gib) == (4, 16)
    assert warning is None


def test_family_fallback_resolves_unknown_variant() -> None:
    spec, warning = get_instance_type("m5a.2xlarge")
    assert (spec.vcpu, spec.memory_gib) == (8, 32)
    assert warning is not None
    assert "m5" in warning


def test_unknown_family_and_size_return_none() -> None:
    assert get_instance_type("x9.zeta") is None
    assert get_instance_type("m5.99xlarge") is None
    assert get_instance_type("t3") is None
