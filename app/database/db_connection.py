"""MySQL connection helper with retry logic and graceful degradation."""
from __future__ import annotations

import os
import time

import mysql.connector
from mysql.connector import Error as MySQLError


def connect_db(retries: int = 5, delay: float = 3.0):
    """Return a live MySQL connection, retrying on transient failures.

    Returns ``None`` instead of raising if the database is still unreachable
    after all attempts, so callers can degrade gracefully rather than crash.
    """
    kwargs = {
        "host":            os.getenv("DB_HOST", "localhost"),
        "user":            os.getenv("DB_USER", "root"),
        "password":        os.getenv("DB_PASSWORD", ""),
        "database":        os.getenv("DB_NAME", "railway"),
        "port":            int(os.getenv("DB_PORT", "3306")),
        "connect_timeout": 10,
    }

    last_exc: MySQLError | None = None
    for attempt in range(1, retries + 1):
        try:
            conn = mysql.connector.connect(**kwargs)
            print(f"[db_connection] Connected to MySQL (attempt {attempt}).")
            return conn
        except MySQLError as exc:
            last_exc = exc
            print(
                f"[db_connection] Connection attempt {attempt}/{retries} failed: {exc}. "
                f"Retrying in {delay}s…"
            )
            time.sleep(delay)

    print(
        f"[db_connection] Could not connect to MySQL after {retries} attempts: {last_exc}. "
        "Returning None — dependent features will be unavailable."
    )
    return None
