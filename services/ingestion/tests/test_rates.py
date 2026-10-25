from datetime import datetime, timedelta, timezone

from app.schemas.sample import Sample
from app.services.rates import RateCalculator

T0 = datetime(2026, 10, 25, 10, 0, 0, tzinfo=timezone.utc)


def sample(seconds, cpu=0.0, req=0.0, lat_sum=0.0, lat_cnt=0.0, mem=50e6, up=True, app="notes-api"):
    return Sample(T0 + timedelta(seconds=seconds), app, up, cpu, mem, req, lat_sum, lat_cnt)


def test_first_sample_gives_nothing():
    assert RateCalculator(6).process(sample(0, cpu=100)) is None


def test_rates_from_two_samples():
    calc = RateCalculator(6)
    calc.process(sample(0, cpu=100.0, req=400, lat_sum=1.0, lat_cnt=400))
    rate = calc.process(sample(5, cpu=100.2, req=430, lat_sum=1.3, lat_cnt=430))
    assert rate.cpu_pct == 4.0            # 0.2 s of CPU in 5 s
    assert rate.req_per_s == 6.0          # 30 requests in 5 s
    assert rate.avg_latency_ms == 10.0    # 0.3 s over 30 requests
    assert rate.memory_mb == 50.0 and rate.reset is False


def test_no_requests_means_no_latency():
    calc = RateCalculator(6)
    calc.process(sample(0, cpu=1, req=10, lat_sum=0.1, lat_cnt=10))
    rate = calc.process(sample(5, cpu=1.1, req=10, lat_sum=0.1, lat_cnt=10))
    assert rate.req_per_s == 0.0 and rate.avg_latency_ms is None


def test_counter_going_down_is_a_reset():
    calc = RateCalculator(6)
    calc.process(sample(0, cpu=100, req=400, lat_cnt=400))
    rate = calc.process(sample(5, cpu=0.3, req=12, lat_cnt=12))   # the app restarted
    assert rate.reset is True and rate.cpu_pct is None and rate.req_per_s is None


def test_gap_is_never_subtracted():
    calc = RateCalculator(6)
    calc.process(sample(0, cpu=100))
    assert calc.process(sample(30, cpu=130)) is None


def test_crash_leaves_a_gap_but_the_reset_is_still_seen():
    calc = RateCalculator(6)
    calc.process(sample(0, cpu=100, req=400, lat_cnt=400))
    assert calc.process(sample(5, up=False)) is None               # down: nothing stored
    rate = calc.process(sample(20, cpu=0.2, req=1, lat_cnt=1))     # back, counters restarted
    assert rate.reset is True


def test_apps_do_not_mix():
    calc = RateCalculator(6)
    calc.process(sample(0, cpu=100, app="notes-api"))
    assert calc.process(sample(5, cpu=0, app="report-api")) is None   # first sample of report-api
