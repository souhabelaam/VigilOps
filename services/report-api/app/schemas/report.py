from datetime import datetime

from pydantic import BaseModel, Field

MAX_LIMIT = 1_000_000


class ReportRequest(BaseModel):
    """What the client sends: count primes up to this number."""

    limit: int = Field(default=200_000, ge=2, le=MAX_LIMIT)


class Report(BaseModel):
    """What the API returns: the answer plus how long the computing took."""

    id: int
    limit: int
    prime_count: int
    duration_seconds: float
    created_at: datetime
