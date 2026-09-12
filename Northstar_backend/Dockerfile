# Northstar Backend — FastAPI API + static SPA
FROM python:3.12-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps (core + optional ML)
COPY requirements.txt . 2>/dev/null || echo "fastapi uvicorn pydantic" > requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Ensure data dir exists (mounted at runtime)
RUN mkdir -p /app/data

EXPOSE 8000

# Cache-only by default — no live gates enabled
ENV SCANNER_LIVE_ALLOWED=false \
    DATAFORSEO_ENABLED=false \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]