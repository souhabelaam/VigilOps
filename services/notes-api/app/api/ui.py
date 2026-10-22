from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

INDEX_FILE = Path(__file__).resolve().parent.parent / "static" / "index.html"


@router.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(INDEX_FILE)
