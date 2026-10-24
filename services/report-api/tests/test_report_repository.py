from app.repositories.report_repository import MAX_REPORTS, ReportRepository


def test_repository_keeps_only_the_latest_reports():
    repo = ReportRepository()
    for _ in range(MAX_REPORTS + 5):
        repo.add(limit=10, prime_count=4, duration_seconds=0.0)

    reports = repo.list_all()
    assert len(reports) == MAX_REPORTS
    # the 5 oldest were dropped, ids keep counting up
    assert reports[0].id == 6
    assert reports[-1].id == MAX_REPORTS + 5
