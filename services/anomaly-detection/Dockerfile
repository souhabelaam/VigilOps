# ---- Stage 1: build. Install dependencies into an isolated folder. ----
FROM python:3.12-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: runtime. Only what is needed to run anomaly-detection. ----
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Run as a normal user, not root.
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY --from=builder /install /usr/local
COPY app ./app
COPY models ./models

USER appuser
CMD ["python", "-m", "app.main"]
