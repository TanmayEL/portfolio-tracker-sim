import sqlite3
from typing import Generator

from pave.config import DB_PATH
from pave.pipeline.store import init_db


def get_db() -> Generator[sqlite3.Connection, None, None]:
    conn = init_db(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()
