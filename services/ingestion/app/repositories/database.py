"""Save Rate rows in PostgreSQL."""
import logging
import time

import psycopg

from app.schemas.sample import Rate

log = logging.getLogger("ingestion.db")

# ON CONFLICT: if the same (app, ts) arrives twice (a message redelivered), keep the first
INSERT = """
INSERT INTO metric_rates (ts, app, cpu_pct, req_per_s, avg_latency_ms, memory_mb, reset)
VALUES (%s, %s, %s, %s, %s, %s, %s)
ON CONFLICT (app, ts) DO NOTHING
"""


class RateRepository:
    def __init__(self, conninfo: str):
        self._conninfo = conninfo
        self._conn: psycopg.Connection | None = None

    def connect(self) -> None:
        """Open the connection, waiting until PostgreSQL is ready."""
        while True:
            try:
                self._conn = psycopg.connect(self._conninfo, autocommit=True)
                log.info("connected to PostgreSQL")
                return
            except psycopg.OperationalError as error:
                log.warning("PostgreSQL not ready (%s), retrying in 3 s", type(error).__name__)
                time.sleep(3)

    def save(self, rate: Rate) -> None:
        """Insert one row; on a broken connection, reconnect and try once more."""
        values = (rate.ts, rate.app, rate.cpu_pct, rate.req_per_s,
                  rate.avg_latency_ms, rate.memory_mb, rate.reset)
        for attempt in (1, 2):
            try:
                self._conn.execute(INSERT, values)
                return
            except (psycopg.OperationalError, AttributeError):
                if attempt == 2:
                    raise
                log.warning("insert failed, reconnecting")
                self.connect()
