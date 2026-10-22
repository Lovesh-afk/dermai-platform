FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TF_CPP_MIN_LOG_LEVEL=2

WORKDIR /srv/ai

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-service.txt .
RUN pip install -r requirements-service.txt

COPY . .

RUN useradd -m appuser && chown -R appuser:appuser /srv/ai
USER appuser

EXPOSE 8001

# start-period is long because TensorFlow + model loading takes a while
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD curl -f http://localhost:8001/health || exit 1

CMD ["python", "-m", "uvicorn", "service.app:app", "--host", "0.0.0.0", "--port", "8001"]
