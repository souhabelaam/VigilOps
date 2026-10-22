from prometheus_client import Counter, Histogram

# Counter: only goes up. Counts every request, split by labels.
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

# Histogram: counts how many requests fell in each duration bucket.
# Custom buckets: this service has slow requests (seconds), not milliseconds.
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30),
)
