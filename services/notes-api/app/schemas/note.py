from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    """What the client sends to create a note."""

    title: str = Field(min_length=1, max_length=100)
    content: str = Field(default="", max_length=5000)


class Note(BaseModel):
    """What the API returns: the note plus fields the server adds."""

    id: int
    title: str
    content: str
    created_at: datetime
