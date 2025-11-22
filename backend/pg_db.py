# backend/pg_db.py
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_NAME = os.getenv("POSTGRES_DB", "hikebot")
DB_USER = os.getenv("POSTGRES_USER", "hikebot")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD", "hikebot")


def _get_conn():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor,
    )


@contextmanager
def get_cursor():
    conn = _get_conn()
    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def fetch_one(query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(query, params or {})
        row = cur.fetchone()
        return dict(row) if row else None


def fetch_all(query: str, params: Optional[Dict[str, Any]] = None) -> Iterable[Dict[str, Any]]:
    with get_cursor() as cur:
        cur.execute(query, params or {})
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def execute(query: str, params: Optional[Dict[str, Any]] = None) -> None:
    with get_cursor() as cur:
        cur.execute(query, params or {})


def fetch_one_returning(query: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """INSERT ... RETURNING ... 这种用这个"""
    with get_cursor() as cur:
        cur.execute(query, params or {})
        row = cur.fetchone()
        if not row:
            raise RuntimeError("No row returned")
        return dict(row)
