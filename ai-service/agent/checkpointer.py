"""Postgres checkpointer for agent runs.

Checkpoints live in their own database (LANGGRAPH_DATABASE_URL), not the app
database: LangGraph creates its own tables, and keeping them out of the
Prisma-managed schema stops `prisma migrate dev` from generating DROP TABLE
statements for them.
"""

import os
import threading

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_lock = threading.Lock()
_saver: PostgresSaver | None = None


class CheckpointerUnavailable(RuntimeError):
    pass


def get_checkpointer() -> PostgresSaver:
    global _saver
    with _lock:
        if _saver is None:
            url = os.getenv("LANGGRAPH_DATABASE_URL")
            if not url:
                raise CheckpointerUnavailable("LANGGRAPH_DATABASE_URL is not configured")

            # prepare_threshold=0 keeps it compatible with PgBouncer-style poolers (Neon).
            pool = ConnectionPool(
                url,
                min_size=1,
                max_size=4,
                kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
                open=True,
            )
            saver = PostgresSaver(pool)
            saver.setup()
            _saver = saver
        return _saver
