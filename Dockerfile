# Backend: FastAPI + TensorFlow model
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    WEB_CONCURRENCY=1

# libgomp: OpenMP runtime used by TensorFlow / scikit-learn
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# dependencies first, so code changes don't reinstall them
COPY requirements-api.txt .
RUN pip install -r requirements-api.txt

# a normal user runs the app and owns the folders written at runtime (uploads, models)
RUN useradd --create-home --uid 1000 freshness

# app code, the dataset split (retraining + insights) and the original model
COPY --chown=freshness:freshness api ./api
COPY --chown=freshness:freshness src ./src
COPY --chown=freshness:freshness data ./data
COPY --chown=freshness:freshness models ./models
RUN mkdir -p data/uploads models/model && chown freshness:freshness data/uploads models models/model
USER freshness

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/', timeout=4)"

# behind Caddy: trust its X-Forwarded-* headers so URLs use https
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY} --proxy-headers --forwarded-allow-ips='*'"]
