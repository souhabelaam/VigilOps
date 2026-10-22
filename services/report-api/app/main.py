import time

from fastapi import FastAPI, Request

from app.api import health, metrics, reports, ui
from app.core.metrics import REQUEST_COUNT, REQUEST_LATENCY

app = FastAPI(title="report-api")


@app.middleware("http")
async def record_metrics(request: Request, call_next):
    """Runs around every request: time it, then update the Prometheus metrics."""
    start = time.perf_counter()
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
app.include_router(reports.router)
app.include_router(ui.router)
