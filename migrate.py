"""Apply checked-in SQL migrations to the configured PostgreSQL database.

Run explicitly as: python migrate.py
This script is not invoked automatically at web-service startup.
"""
from __future__ import annotations

import os
from pathlib import Path

import psycopg


def main() -> None:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is not configured; refusing to run migrations.")
    migration = Path(__file__).parent / "migrations" / "001_connection_center.sql"
    sql = migration.read_text(encoding="utf-8")
    # The migration contains only fixed, reviewed DDL; no user input is interpolated.
    with psycopg.connect(database_url, connect_timeout=10) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
    print("Connection Center schema migration 001 applied.")


if __name__ == "__main__":
    main()
