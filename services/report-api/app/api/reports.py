from fastapi import APIRouter, status

from app.repositories.report_repository import ReportRepository
from app.schemas.report import Report, ReportRequest
from app.services.report_service import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])

# One repository for the whole process, so history persists between requests.
_service = ReportService(ReportRepository())


# A plain `def` (not `async def`): FastAPI runs it in a worker thread, so the
# CPU-heavy loop does not freeze the whole server while it computes.
@router.post("", response_model=Report, status_code=status.HTTP_201_CREATED)
def create_report(data: ReportRequest) -> Report:
    return _service.create_report(data)


@router.get("", response_model=list[Report])
def list_reports() -> list[Report]:
    return _service.list_reports()
