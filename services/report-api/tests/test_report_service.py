from app.services.report_service import count_primes


def test_count_primes_small():
    # primes up to 10: 2, 3, 5, 7
    assert count_primes(10) == 4


def test_count_primes_known_value():
    assert count_primes(100) == 25


def test_count_primes_edge_case_below_two():
    # 1 is not prime, so the loop never runs and the count stays 0
    assert count_primes(1) == 0
