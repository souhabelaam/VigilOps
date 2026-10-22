from datetime import datetime, timezone

from app.schemas.report import Report


class ReportRepository:
    """Storage layer: keeps finished reports in memory. Lost on restart."""

    def __init__(self) -> None:
        self._reports: dict[int, Report] = {}
        self._next_id = 1

    def add(self, limit: int, prime_count: int, duration_seconds: float) -> Report:
        report = Report(
            id=self._next_id,
            limit=limit,
            prime_count=prime_count,
            duration_seconds=duration_seconds,
            created_at=datetime.now(timezone.utc),
        )
        self._reports[report.id] = report
        self._next_id += 1
        return report

    def list_all(self) -> list[Report]:
        return list(self._reports.values())
