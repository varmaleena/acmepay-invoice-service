FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && groupadd --system acmepay \
    && useradd --system --gid acmepay --no-create-home acmepay

COPY backend/ backend/
COPY frontend_sdk/ frontend_sdk/
COPY docs/ docs/

USER acmepay
EXPOSE 8001
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8001"]
