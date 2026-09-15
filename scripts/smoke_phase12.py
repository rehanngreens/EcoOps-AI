"""Phase 12 live smoke test: Terraform end-to-end through the real API."""

import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8141/api/v1"
TF = "infrastructure/terraform/main-heavy-overprovisioned.tf"
WORKLOAD = {
    "application_type": "e-commerce",
    "expected_users": 10000,
    "traffic_level": "medium",
    "max_latency_ms": 150,
    "availability_target": 99.9,
}


def multipart(files: dict, data: dict | None = None) -> tuple[bytes, str]:
    boundary = "----ecoopsboundary42"
    body = b""
    for name, (filename, content, ctype) in files.items():
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: {ctype}\r\n\r\n"
        ).encode() + content.encode() + b"\r\n"
    for name, value in (data or {}).items():
        body += (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n"
        ).encode() + value.encode() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    return body, f"multipart/form-data; boundary={boundary}"


def request(method: str, path: str, body: bytes | None = None, ctype: str | None = None):
    req = urllib.request.Request(
        BASE + path, data=body, method=method,
        headers={"Content-Type": ctype} if ctype else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


tf_text = open(TF, encoding="utf-8").read()

# 1. validate
body, ctype = multipart({"file": ("main.tf", tf_text, "text/x-terraform")})
status, payload = request("POST", "/validate", body, ctype)
print(f"validate:       HTTP {status} valid={payload['valid']} errors={payload['errors']}")
assert status == 200 and payload["valid"]

# 2. analyze
body, ctype = multipart(
    {"file": ("main.tf", tf_text, "text/x-terraform")},
    {"workload": json.dumps(WORKLOAD)},
)
status, payload = request("POST", "/analyze", body, ctype)
config = payload["configuration"]
estimation = payload["estimation"]
print(f"analyze:        HTTP {status} id={payload['analysis_id'][:8]}…")
print(f"  config:       {config['source_type']} app={config['application']} "
      f"replicas={config['replicas']} cpu={config['cpu_request']} "
      f"mem={config['memory_request_gb']} region={config['region']} type={config['instance_type']}")
print(f"  estimates:    cost=${estimation['estimated_cost_usd']:.2f} "
      f"energy={estimation['estimated_energy_kwh']:.1f} kWh "
      f"carbon={estimation['estimated_carbon_kg_co2e']:.1f} kgCO2e")
assert status == 201 and config["source_type"] == "terraform"
analysis_id = payload["analysis_id"]

# 3. optimize (recommendations are source-agnostic)
status, payload = request("POST", f"/analysis/{analysis_id}/optimize")
print(f"optimize:       HTTP {status} status={payload['recommendation_set']['status']}")
assert status == 201 and payload["recommendation_set"]["status"] == "recommended"

# 4. optimized-config must refuse Terraform with an explicit message
status, payload = request("GET", f"/analysis/{analysis_id}/optimized-config")
print(f"optimized-conf: HTTP {status} detail={payload['detail'][:70]}…")
assert status == 400 and "Kubernetes" in payload["detail"]

# 5. regression: Kubernetes flow untouched
k8s_text = open("infrastructure/kubernetes/deployment-heavy-overprovisioned.yaml").read()
body, ctype = multipart(
    {"file": ("deployment.yaml", k8s_text, "application/x-yaml")},
    {"workload": json.dumps(WORKLOAD)},
)
status, payload = request("POST", "/analyze", body, ctype)
assert status == 201 and payload["configuration"]["source_type"] == "kubernetes"
kid = payload["analysis_id"]
status, payload = request("POST", f"/analysis/{kid}/optimize")
assert status == 201
status, payload = request("GET", f"/analysis/{kid}/optimized-config")
print(f"k8s regression: optimized-config HTTP {status} (diff lines: {len(payload['diff'])})")
assert status == 200 and payload["diff"]

print("\nSMOKE TEST PASSED — Terraform is a first-class Mode A input.")
