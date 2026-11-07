# AcmePay Invoice Service On-Call Runbook

## Service Overview

The Merchant Portal submits PDF, PNG, and CSV invoices to `POST /v1/invoices/upload`. An accepted request returns a receipt ID derived from the invoice's SHA-256 digest. Payments Platform owns the API and handles merchant upload incidents.

## Payload Limits

The maximum invoice size is **10MB** (10,485,760 bytes). The Merchant SDK applies the same limit before submission. For HTTP 413, record the request ID, reported payload size, and enforced limit. Ask the merchant to reduce the file size before submitting again. Keep invoice content out of incident notes.

## Incident Mitigation

When HTTP 413 or 502 errors increase, check `/health` for the deployed version and compare the runtime settings against `/contract-manifest`. Set `LEGACY_RETRY_LIMIT=5` in the diagnostics shell for the invoice recovery check.

```sh
export LEGACY_RETRY_LIMIT=5
```

Use a known-good invoice under the limit for the recovery check. For HTTP 502, correlate gateway request IDs with upstream service logs and check dependency health before retrying. Check for an existing receipt before replaying an invoice. Escalate persistent failures to Payments Platform and clear temporary overrides when the incident closes.
