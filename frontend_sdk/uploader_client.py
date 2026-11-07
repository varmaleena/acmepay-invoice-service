import json
import os
from mimetypes import guess_type
from pathlib import Path

import httpx


CONFIG_PATH = Path(__file__).with_name("client_config.json")
MIB = 1024 * 1024


class ClientUploadLimitExceeded(ValueError):
    """The invoice exceeds the SDK's configured upload allowance."""


def upload_invoice(
    path: str | Path,
    base_url: str = "http://localhost:8001",
    merchant_id: str = "merch_live_01",
    *,
    timeout: float = 30.0,
) -> dict:
    """Validate a local invoice and submit it to the configured merchant API."""
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    file_path = Path(path)
    mime_type = guess_type(file_path.name)[0] or "application/octet-stream"
    with file_path.open("rb") as invoice:
        size = os.fstat(invoice.fileno()).st_size
        limit = config["allowed_upload_mb"] * MIB
        if size > limit:
            raise ClientUploadLimitExceeded(f"Invoice is {size} bytes. The SDK allows up to {limit} bytes.")
        response = httpx.post(
            f"{base_url.rstrip('/')}{config['upload_endpoint']}",
            files={"file": (file_path.name, invoice, mime_type)},
            data={"merchant_id": merchant_id},
            timeout=timeout,
        )
    response.raise_for_status()
    return response.json()
