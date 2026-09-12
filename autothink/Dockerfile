# AutothinK Backend — local brain server
FROM python:3.12-slim

WORKDIR /app

# System deps for ollama client + any native wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY backend ./backend
COPY orchestration ./orchestration
COPY memory ./memory
COPY ui ./ui

EXPOSE 8100

CMD ["python", "-m", "uvicorn", "backend.server:app", "--host", "0.0.0.0", "--port", "8100", "--log-level", "info"]