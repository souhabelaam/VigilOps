from datetime import datetime, timezone

from app.schemas.note import Note, NoteCreate


class NoteRepository:
    """Storage layer: keeps notes in memory (a dict). Lost on restart."""

    def __init__(self) -> None:
        self._notes: dict[int, Note] = {}
        self._next_id = 1

    def add(self, data: NoteCreate) -> Note:
        note = Note(
            id=self._next_id,
            title=data.title,
            content=data.content,
            created_at=datetime.now(timezone.utc),
        )
        self._notes[note.id] = note
        self._next_id += 1
        return note

    def list_all(self) -> list[Note]:
        return list(self._notes.values())

    def delete(self, note_id: int) -> bool:
        return self._notes.pop(note_id, None) is not None
