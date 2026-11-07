# acmepay-invoice-service

AcmePay Merchant Invoice Processing API and Python uploader SDK. The API measures multipart invoices in bytes and returns a receipt derived from the file's SHA-256 digest.

## Local development

```sh
python -m venv .venv
python -m pip install -r requirements.txt
python -m pytest tests/test_backend_unit.py
python -m uvicorn backend.app:app --port 8001
```

Activate `.venv` before installing dependencies, running tests, or starting the API. Set `ACMEPAY_CORS_ORIGINS` to a comma-separated list of approved web origins. The development default permits the local merchant portal on port 3000.

## API

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | Runtime policy and current Git revision when available |
| GET | `/contract-manifest` | Live backend policy, SDK configuration, and on-call runbook |
| POST | `/v1/invoices/upload` | Multipart invoice verification using `file` and optional `merchant_id` |

Size settings expressed as MB use 1,048,576 bytes per unit. The backend responds with HTTP 413 and `PAYLOAD_CONTRACT_VIOLATION` when the file exceeds the current runtime policy.

```python
from frontend_sdk.uploader_client import upload_invoice

receipt = upload_invoice("invoice.pdf", merchant_id="merch_live_01")
print(receipt["receipt_id"])
```

## Container

```sh
docker build -t acmepay-invoice-service .
docker run --rm -p 8001:8001 acmepay-invoice-service
```
