from fastapi import APIRouter, HTTPException, status

from app.repositories.note_repository import NoteRepository
from app.schemas.note import Note, NoteCreate
from app.services.note_service import NoteNotFoundError, NoteService

router = APIRouter(prefix="/notes", tags=["notes"])

# One repository for the whole process, so notes persist between requests.
_service = NoteService(NoteRepository())


@router.post("", response_model=Note, status_code=status.HTTP_201_CREATED)
def create_note(data: NoteCreate) -> Note:
    return _service.create_note(data)


@router.get("", response_model=list[Note])
def list_notes() -> list[Note]:
    return _service.list_notes()


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: int) -> None:
    try:
        _service.delete_note(note_id)
    except NoteNotFoundError:
        raise HTTPException(status_code=404, detail="Note not found")
