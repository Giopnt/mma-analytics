import logging
import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

log = logging.getLogger(__name__)


def get_conn():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5433")),
        dbname=os.getenv("DB_NAME", "mma_warehouse"),
        user=os.getenv("DB_USER", "mma"),
        password=os.getenv("DB_PASSWORD", "mma_pass"),
    )


@contextmanager
def transaction(conn):
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def get_or_create_fighter(cur, name: str) -> int:
    cur.execute(
        "INSERT INTO dim_fighter (name) VALUES (%s) ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING fighter_id",
        (name,),
    )
    return cur.fetchone()[0]


def get_or_create_method(cur, method: str, detail: str) -> int:
    cur.execute(
        "INSERT INTO dim_method (method, method_detail) VALUES (%s, %s) ON CONFLICT (method, method_detail) DO UPDATE SET method = EXCLUDED.method RETURNING method_id",
        (method, detail or ""),
    )
    return cur.fetchone()[0]
