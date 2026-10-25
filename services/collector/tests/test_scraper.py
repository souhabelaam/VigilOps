from app.services.scraper import parse_metrics, scrape

TEXT = """# HELP process_cpu_seconds_total Total CPU time
# TYPE process_cpu_seconds_total counter
process_cpu_seconds_total 6.3
process_resident_memory_bytes 2.6e+07
http_requests_total{method="GET",path="/notes",status="200"} 4.0
http_requests_total{method="POST",path="/notes",status="201"} 2.0
http_requests_total{method="GET",path="/metrics",status="200"} 99.0
http_requests_total{method="GET",path="/health",status="200"} 50.0
http_request_duration_seconds_sum{method="GET",path="/notes"} 0.6
http_request_duration_seconds_count{method="GET",path="/notes"} 6.0
http_request_duration_seconds_sum{method="GET",path="/metrics"} 70.0
http_request_duration_seconds_count{method="GET",path="/metrics"} 99.0
"""


def test_parse_reads_counters_and_memory():
    s = parse_metrics(TEXT, "notes-api", "2026-10-25T10:00:00+00:00")
    assert s.up is True
    assert s.cpu_seconds_total == 6.3
    assert s.memory_bytes == 2.6e7


def test_parse_ignores_metrics_and_health_paths():
    s = parse_metrics(TEXT, "notes-api", "t")
    assert s.requests_total == 6.0          # 4 + 2, not the 99 + 50 of our own visits
    assert s.latency_count == 6.0
    assert s.latency_sum_seconds == 0.6


def test_parse_app_without_requests_yet():
    s = parse_metrics("process_cpu_seconds_total 1.0\n", "report-api", "t")
    assert s.requests_total == 0.0 and s.up is True


def test_unreachable_app_gives_up_false():
    s = scrape("notes-api", "http://127.0.0.1:1", timeout=0.5)
    assert s.up is False and s.cpu_seconds_total == 0.0
