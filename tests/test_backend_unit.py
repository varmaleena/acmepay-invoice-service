from hashlib import sha256

from fastapi.testclient import TestClient

from backend.app import MIB, app, load_policy


client = TestClient(app)


def test_health_reports_runtime_policy():
    policy = load_policy()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json().items() >= {
        "service_name": policy.SERVICE_NAME,
        "version": policy.VERSION,
        "enforced_max_upload_mb": policy.MAX_UPLOAD_MB,
        "active_retry_env_var": policy.RETRY_ENV_VAR,
    }.items()


def test_manifest_exposes_runtime_and_external_contracts():
    response = client.get("/contract-manifest")
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["backend"] == load_policy().model_dump()
    assert manifest["frontend_sdk"]["upload_endpoint"] == "/v1/invoices/upload"
    assert "## Incident Mitigation" in manifest["runbook"]


def test_one_mb_pdf_is_accepted():
    pdf_header = b"%PDF-1.7\n"
    content = pdf_header + bytes(MIB - len(pdf_header))
    response = client.post("/v1/invoices/upload", files={"file": ("invoice.pdf", content, "application/pdf")})
    assert response.status_code == 200
    assert response.json() == {
        "receipt_id": sha256(content).hexdigest()[:24],
        "received_mb": 1,
        "status": "ACCEPTED",
    }


def test_binary_upload_one_byte_over_limit_is_rejected():
    policy = load_policy()
    size = policy.MAX_UPLOAD_MB * MIB + 1
    response = client.post(
        "/v1/invoices/upload",
        files={"file": ("invoice.pdf", bytes(size), "application/pdf")},
        data={"merchant_id": "merch_test"},
    )
    assert response.status_code == 413
    assert response.json()["detail"] == {
        "error_code": "PAYLOAD_CONTRACT_VIOLATION",
        "received_mb": size / MIB,
        "enforced_max_upload_mb": policy.MAX_UPLOAD_MB,
        "active_retry_env_var": policy.RETRY_ENV_VAR,
    }


def test_sdk_origin_can_preflight_uploads():
    origin = "http://localhost:3000"
    response = client.options("/v1/invoices/upload", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
