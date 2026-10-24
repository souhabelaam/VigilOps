import asyncio
import time

from fastapi import FastAPI, Request

from app.api import faults as faults_api
from app.api import health, metrics, notes, ui
from app.core.faults import faults
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY

EXEMPT_PATHS = ("/faults", "/metrics", "/health")

app = FastAPI(title="notes-api")


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    """Runs around every request: time it, then update the Prometheus metrics."""
    start = time.perf_counter()
    # Slow-response fault: delay business requests, never the tooling endpoints.
    if faults.latency_seconds and not request.url.path.startswith(EXEMPT_PATHS):
        await asyncio.sleep(faults.latency_seconds)
    response = await call_next(request)
    duration = time.perf_counter() - start

    # Use the route template, and one fixed label for unknown paths,
    # so the number of label values stays small.
    route = request.scope.get("route")
    path = route.path if route else "unmatched"

    REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(duration)
    return response


app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(faults_api.router)
app.include_router(notes.router)
app.include_router(ui.router)
