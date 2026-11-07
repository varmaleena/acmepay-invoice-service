import ast
import json
import logging
import os
import subprocess
from hashlib import sha256
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field


ROOT = Path(__file__).resolve().parents[1]
MIB = 1024 * 1024
logger = logging.getLogger(__name__)


class RuntimePolicy(BaseModel):
    model_config = ConfigDict(strict=True)

    SERVICE_NAME: str = Field(min_length=1)
    VERSION: str = Field(min_length=1)
    MAX_UPLOAD_MB: int = Field(gt=0)
    RETRY_ENV_VAR: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    DEFAULT_RETRIES: int = Field(ge=0)


class ClientContract(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow")

    sdk_name: str
    sdk_version: str
    allowed_upload_mb: int = Field(gt=0)
    expected_retry_env: str
    upload_endpoint: str
    allowed_mime_types: list[str]


def load_policy() -> RuntimePolicy:
    """Read only the policy's literal assignments so live inspection and enforcement agree."""
    try:
        tree = ast.parse((ROOT / "backend" / "config.py").read_text(encoding="utf-8"))
        values = {}
        for statement in tree.body:
            if not isinstance(statement, ast.Assign):
                continue
            for target in statement.targets:
                if isinstance(target, ast.Name) and target.id in RuntimePolicy.model_fields:
                    values[target.id] = ast.literal_eval(statement.value)
        return RuntimePolicy.model_validate(values)
    except (OSError, SyntaxError, ValueError, TypeError) as exc:
        logger.exception("Invoice runtime policy could not be loaded")
        raise HTTPException(503, detail="Invoice runtime policy is unavailable.") from exc


def git_ref(*args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=True, timeout=2,
        )
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


app = FastAPI(title="AcmePay Invoice Service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in os.getenv(
            "ACMEPAY_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
        ).split(",") if origin.strip()
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health():
    policy = load_policy()
    return {
        "service_name": policy.SERVICE_NAME,
        "version": policy.VERSION,
        "enforced_max_upload_mb": policy.MAX_UPLOAD_MB,
        "active_retry_env_var": policy.RETRY_ENV_VAR,
        "git_branch": git_ref("rev-parse", "--abbrev-ref", "HEAD"),
        "git_commit_sha": git_ref("rev-parse", "HEAD"),
    }


@app.get("/contract-manifest")
def contract_manifest():
    policy = load_policy()
    try:
        sdk = ClientContract.model_validate(json.loads(
            (ROOT / "frontend_sdk" / "client_config.json").read_text(encoding="utf-8")
        ))
        runbook = (ROOT / "docs" / "oncall-runbook.md").read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        logger.exception("Invoice contract files could not be loaded")
        raise HTTPException(503, detail="Invoice contract files are unavailable.") from exc
    return {"backend": policy.model_dump(), "frontend_sdk": sdk.model_dump(), "runbook": runbook}


@app.post("/v1/invoices/upload")
async def upload_invoice(
    file: UploadFile = File(...),
    merchant_id: str = Form("merch_live_01", min_length=1, max_length=128),
):
    policy = await run_in_threadpool(load_policy)
    content = await file.read()
    received_mb = len(content) / MIB
    digest = sha256(content).hexdigest()
    if len(content) > policy.MAX_UPLOAD_MB * MIB:
        logger.info("Rejected invoice upload merchant_id=%r bytes=%d", merchant_id, len(content))
        raise HTTPException(status_code=413, detail={
            "error_code": "PAYLOAD_CONTRACT_VIOLATION",
            "received_mb": received_mb,
            "enforced_max_upload_mb": policy.MAX_UPLOAD_MB,
            "active_retry_env_var": policy.RETRY_ENV_VAR,
        })
    logger.info("Accepted invoice upload merchant_id=%r receipt_id=%s bytes=%d", merchant_id, digest[:24], len(content))
    return {"receipt_id": digest[:24], "received_mb": received_mb, "status": "ACCEPTED"}
