from app.repositories.note_repository import NoteRepository
from app.schemas.note import Note, NoteCreate


class NoteNotFoundError(Exception):
    """Raised when a note id does not exist."""


class NoteService:
    """Business rules layer. Knows nothing about HTTP."""

    def __init__(self, repository: NoteRepository) -> None:
        self._repository = repository

    def create_note(self, data: NoteCreate) -> Note:
        return self._repository.add(data)

    def list_notes(self) -> list[Note]:
        return self._repository.list_all()

    def delete_note(self, note_id: int) -> None:
        if not self._repository.delete(note_id):
            raise NoteNotFoundError(note_id)
