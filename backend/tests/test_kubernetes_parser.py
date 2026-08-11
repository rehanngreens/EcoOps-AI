import pytest

from app.parsers.kubernetes_parser import KubernetesParserError, parse_kubernetes_yaml
from tests.conftest import load_manifest


@pytest.mark.parametrize(
    ("manifest_name", "expected"),
    [
        (
            "deployment-well-provisioned.yaml",
            {
                "source_type": "kubernetes",
                "application": "api-backend",
                "namespace": "ecommerce",
                "replicas": 2,
                "cpu_request": 0.5,
                "cpu_limit": 1.0,
                "memory_request_gb": 0.5,
                "memory_limit_gb": 2.0,
                "autoscaling_enabled": False,
                "container_image": "ecommerce/api-backend:1.0.0",
            },
        ),
        (
            "deployment-moderate-overprovisioned.yaml",
            {
                "source_type": "kubernetes",
                "application": "api-backend",
                "namespace": "ecommerce",
                "replicas": 4,
                "cpu_request": 2.0,
                "cpu_limit": 4.0,
                "memory_request_gb": 4.0,
                "memory_limit_gb": 8.0,
                "autoscaling_enabled": False,
                "container_image": "ecommerce/api-backend:1.0.0",
            },
        ),
        (
            "deployment-heavy-overprovisioned.yaml",
            {
                "source_type": "kubernetes",
                "application": "api-backend",
                "namespace": "ecommerce",
                "replicas": 8,
                "cpu_request": 8.0,
                "cpu_limit": 8.0,
                "memory_request_gb": 16.0,
                "memory_limit_gb": 16.0,
                "autoscaling_enabled": False,
                "container_image": "ecommerce/api-backend:1.0.0",
            },
        ),
        (
            "deployment-edge-case.yaml",
            {
                "source_type": "kubernetes",
                "application": "sidecar-app",
                "namespace": "default",
                "replicas": 1,
                "cpu_request": 0.5,
                "cpu_limit": 1.0,
                "memory_request_gb": 0.5,
                "memory_limit_gb": 1.0,
                "autoscaling_enabled": False,
                "container_image": "myapp:1.0.0",
            },
        ),
    ],
)
def test_parse_sample_manifests(manifest_name: str, expected: dict) -> None:
    result = parse_kubernetes_yaml(load_manifest(manifest_name))
    assert result == expected


def test_parse_defaults_namespace_and_replicas() -> None:
    yaml_text = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minimal-app
spec:
  template:
    spec:
      containers:
        - name: app
          image: minimal:1.0.0
          resources:
            requests:
              cpu: "1"
              memory: "1Gi"
            limits:
              cpu: "2"
              memory: "2Gi"
"""
    result = parse_kubernetes_yaml(yaml_text)
    assert result["namespace"] == "default"
    assert result["replicas"] == 1


def test_rejects_unsupported_kind() -> None:
    yaml_text = """
apiVersion: v1
kind: Service
metadata:
  name: web
"""
    with pytest.raises(KubernetesParserError, match="Unsupported resource kind"):
        parse_kubernetes_yaml(yaml_text)


def test_rejects_invalid_yaml() -> None:
    with pytest.raises(KubernetesParserError, match="Invalid YAML syntax"):
        parse_kubernetes_yaml("apiVersion: [unclosed")


def test_rejects_missing_deployment_name() -> None:
    yaml_text = """
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: app
          image: app:1.0.0
"""
    with pytest.raises(KubernetesParserError, match="metadata.name is required"):
        parse_kubernetes_yaml(yaml_text)


def test_rejects_missing_containers() -> None:
    yaml_text = """
apiVersion: apps/v1
kind: Deployment
metadata:
  name: empty-app
spec:
  template:
    spec:
      containers: []
"""
    with pytest.raises(KubernetesParserError, match="at least one container"):
        parse_kubernetes_yaml(yaml_text)
