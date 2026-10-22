import time

from app.repositories.report_repository import ReportRepository
from app.schemas.report import Report, ReportRequest


def count_primes(limit: int) -> int:
    """Count primes up to `limit` by trial division.

    This is deliberately the slow, naive method: it keeps the CPU busy,
    which gives the monitoring system real load to detect.
    """
    count = 0
    for n in range(2, limit + 1):
        is_prime = True
        divisor = 2
        while divisor * divisor <= n:
            if n % divisor == 0:
                is_prime = False
                break
            divisor += 1
        if is_prime:
            count += 1
    return count


class ReportService:
    """Business rules layer. Knows nothing about HTTP."""

    def __init__(self, repository: ReportRepository) -> None:
        self._repository = repository

    def create_report(self, data: ReportRequest) -> Report:
        start = time.perf_counter()
        prime_count = count_primes(data.limit)
        duration = time.perf_counter() - start
        return self._repository.add(data.limit, prime_count, round(duration, 4))

    def list_reports(self) -> list[Report]:
        return self._repository.list_all()
