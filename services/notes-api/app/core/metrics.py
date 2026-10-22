from prometheus_client import Counter, Histogram

# Counter: only goes up. Counts every request, split by labels.
REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)

# Histogram: counts how many requests fell in each duration bucket.
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "path"],
)
