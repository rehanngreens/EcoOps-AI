"""Tests for the Phase 12 Terraform parser (HCL subset)."""

import pytest

from app.parsers.terraform_parser import TerraformParserError, parse_terraform, validate_terraform
from tests.conftest import load_terraform

WELL_EXPECTED = {
    "source_type": "terraform",
    "application": "api-backend",
    "namespace": "default",
    "replicas": 2,
    "cpu_request": 2.0,
    "cpu_limit": None,
    "memory_request_gb": 4.0,
    "memory_limit_gb": None,
    "autoscaling_enabled": False,
    "container_image": None,
    "cloud_provider": "aws",
    "region": "ap-south-1",
    "instance_type": "t3.medium",
    "instance_count": 2,
    "storage_gb": 20.0,
}

HEAVY_EXPECTED = {
    "source_type": "terraform",
    "application": "web-frontend",
    "namespace": "default",
    "replicas": 8,
    "cpu_request": 8.0,
    "cpu_limit": None,
    "memory_request_gb": 32.0,
    "memory_limit_gb": None,
    "autoscaling_enabled": False,
    "container_image": None,
    "cloud_provider": "aws",
    "region": "ap-south-1",
    "instance_type": "m5.2xlarge",
    "instance_count": 8,
    "storage_gb": 100.0,
}


@pytest.mark.parametrize(
    ("manifest_name", "expected"),
    [
        ("main-well-provisioned.tf", WELL_EXPECTED),
        ("main-heavy-overprovisioned.tf", HEAVY_EXPECTED),
    ],
)
def test_parse_sample_configurations(manifest_name: str, expected: dict) -> None:
    assert parse_terraform(load_terraform(manifest_name)) == expected


def test_moderate_demo_parses() -> None:
    result = parse_terraform(load_terraform("main-moderate-overprovisioned.tf"))
    assert result["replicas"] == 3
    assert result["instance_type"] == "t3.large"
    assert result["cpu_request"] == 2.0
    assert result["memory_request_gb"] == 8.0


def test_defaults_count_and_uses_resource_label_for_name() -> None:
    tf_text = """
resource "aws_instance" "worker" {
  instance_type = "c5.large"
}
"""
    result = parse_terraform(tf_text)
    assert result["replicas"] == 1
    assert result["application"] == "worker"
    assert result["cpu_request"] == 2.0
    assert result["memory_request_gb"] == 4.0
    assert result["storage_gb"] is None
    assert "region" not in result
    assert result.get("parser_warnings") is None


def test_tags_name_wins_over_resource_label() -> None:
    tf_text = """
resource "aws_instance" "api" {
  instance_type = "t3.small"
  tags = {
    Name = "real-name"
    Env  = "prod"
  }
}
"""
    assert parse_terraform(tf_text)["application"] == "real-name"


def test_autoscaling_group_enables_autoscaling() -> None:
    tf_text = """
resource "aws_instance" "api" {
  instance_type = "t3.medium"
}

resource "aws_autoscaling_group" "web" {
  min_size = 1
  max_size = 4
}
"""
    assert parse_terraform(tf_text)["autoscaling_enabled"] is True


def test_comments_are_ignored() -> None:
    tf_text = """
# resource "aws_instance" "ghost" {
#   instance_type = "m5.4xlarge"
# }
resource "aws_instance" "real" { # trailing comment
  instance_type = "t3.medium" // another comment
}
"""
    result = parse_terraform(tf_text)
    assert result["application"] == "real"
    assert result["instance_type"] == "t3.medium"


def test_unknown_instance_type_is_rejected() -> None:
    tf_text = """
resource "aws_instance" "api" {
  instance_type = "x9.zeta"
}
"""
    with pytest.raises(TerraformParserError, match="Unknown EC2 instance type"):
        parse_terraform(tf_text)


def test_missing_instance_type_is_rejected() -> None:
    tf_text = """
resource "aws_instance" "api" {
  ami = "ami-123"
}
"""
    with pytest.raises(TerraformParserError, match="instance_type"):
        parse_terraform(tf_text)


def test_no_resource_blocks_is_rejected() -> None:
    with pytest.raises(TerraformParserError, match="No resource blocks"):
        parse_terraform("provider \"aws\" {\n  region = \"us-east-1\"\n}")


def test_unsupported_resource_only_is_rejected() -> None:
    tf_text = """
resource "aws_launch_template" "web" {
  instance_type = "t3.medium"
}
"""
    with pytest.raises(TerraformParserError, match="aws_launch_template"):
        parse_terraform(tf_text)


def test_multiple_instances_are_rejected() -> None:
    tf_text = """
resource "aws_instance" "one" {
  instance_type = "t3.medium"
}

resource "aws_instance" "two" {
  instance_type = "t3.medium"
}
"""
    with pytest.raises(TerraformParserError, match="Multiple aws_instance"):
        parse_terraform(tf_text)


def test_interpolation_is_rejected() -> None:
    tf_text = """
resource "aws_instance" "api" {
  instance_type = var.instance_type
  count         = var.count
}
"""
    with pytest.raises(TerraformParserError, match="variables and references are not supported"):
        parse_terraform(tf_text)


def test_interpolated_string_is_rejected() -> None:
    tf_text = """
resource "aws_instance" "api" {
  instance_type = "${var.type}"
}
"""
    with pytest.raises(TerraformParserError, match="interpolation"):
        parse_terraform(tf_text)


def test_bad_count_is_rejected() -> None:
    tf_text = """
resource "aws_instance" "api" {
  instance_type = "t3.medium"
  count         = 0
}
"""
    with pytest.raises(TerraformParserError, match="count"):
        parse_terraform(tf_text)


def test_unbalanced_braces_are_rejected() -> None:
    tf_text = """
resource "aws_instance" "api" {
  instance_type = "t3.medium"
"""
    with pytest.raises(TerraformParserError, match="[Uu]nbalanced"):
        parse_terraform(tf_text)


def test_validate_returns_error_list() -> None:
    assert validate_terraform("not terraform at all") != []
    tf_text = """
resource "aws_instance" "api" {
  instance_type = "t3.medium"
}
"""
    assert validate_terraform(tf_text) == []
