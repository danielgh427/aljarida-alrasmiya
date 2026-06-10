"""Database bootstrap — creates the database and schema if they don't exist.

Called once at application startup before any connection that specifies a
database name is attempted.  Safe to call on every restart because every
DDL statement uses IF NOT EXISTS.
"""
from __future__ import annotations

import os
import sys
import time

import mysql.connector
from mysql.connector import Error as MySQLError

# ---------------------------------------------------------------------------
# Resolve project root so this module works regardless of working directory
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))  # …/app/database → project root
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def _get_conn_kwargs(*, with_database: bool = True) -> dict:
    """Return mysql.connector keyword arguments from environment variables."""
    kwargs: dict = {
        "host":             os.getenv("DB_HOST", "localhost"),
        "user":             os.getenv("DB_USER", "root"),
        "password":         os.getenv("DB_PASSWORD", ""),
        "port":             int(os.getenv("DB_PORT", "3306")),
        "connect_timeout":  10,
    }
    if with_database:
        kwargs["database"] = os.getenv("DB_NAME", "railway")
    return kwargs


def _wait_for_mysql(retries: int = 10, delay: float = 3.0) -> None:
    """Block until MySQL is reachable (without selecting a database)."""
    kwargs = _get_conn_kwargs(with_database=False)
    for attempt in range(1, retries + 1):
        try:
            conn = mysql.connector.connect(**kwargs)
            conn.close()
            print(f"[init_db] MySQL is reachable (attempt {attempt}).")
            return
        except MySQLError as exc:
            print(
                f"[init_db] MySQL not ready yet (attempt {attempt}/{retries}): {exc}. "
                f"Retrying in {delay}s…"
            )
            time.sleep(delay)
    raise RuntimeError(
        f"[init_db] Could not reach MySQL after {retries} attempts. Aborting."
    )


def init_db() -> None:
    """Ensure the target database and all tables exist.

    Steps
    -----
    1. Wait until the MySQL server is reachable.
    2. Connect *without* a database and CREATE DATABASE IF NOT EXISTS.
    3. Re-connect *with* the database and run the schema DDL.
    """
    db_name = os.getenv("DB_NAME", "railway")

    # ── 1. Wait for the server ──────────────────────────────────────
    _wait_for_mysql()

    # ── 2. Create the database if it doesn't exist ──────────────────
    try:
        conn = mysql.connector.connect(**_get_conn_kwargs(with_database=False))
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
        cursor.close()
        conn.close()
        print(f"[init_db] Database `{db_name}` is ready.")
    except MySQLError as exc:
        raise RuntimeError(f"[init_db] Failed to create database `{db_name}`: {exc}") from exc

    # ── 3. Apply schema (idempotent — all statements use IF NOT EXISTS) ──
    schema_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "schema.sql"
    )

    try:
        conn = mysql.connector.connect(**_get_conn_kwargs(with_database=True))
        cursor = conn.cursor()

        with open(schema_path, "r", encoding="utf-8") as fh:
            sql_script = fh.read()

        for statement in sql_script.split(";"):
            stmt = statement.strip()
            if stmt and not stmt.startswith("--"):
                cursor.execute(stmt)

        conn.commit()
        cursor.close()
        conn.close()
        print("[init_db] Schema applied successfully.")
    except MySQLError as exc:
        raise RuntimeError(f"[init_db] Failed to apply schema: {exc}") from exc
