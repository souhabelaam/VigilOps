import time

from fastapi import FastAPI, Request

from app.api import health, metrics, notes, ui
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY

app = FastAPI(title="notes-api")


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    """Runs around every request: time it, then update the Prometheus metrics."""
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start

    # Use the route template (/notes/{note_id}), not the raw URL, so labels stay few.
    route = request.scope.get("route")
    path = route.path if route else request.url.path

    REQUEST_COUNT.labels(request.method, path, response.status_code).inc()
    REQUEST_LATENCY.labels(request.method, path).observe(duration)
    return response


app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(notes.router)
app.include_router(ui.router)
