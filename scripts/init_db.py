#!/usr/bin/env python3
"""
Database initialization script.

Connects to MySQL using credentials from config.py and executes schema.sql
to create necessary tables. Designed to be run as a Railway Post-Deploy Command.
"""
from __future__ import annotations

import os
import sys
import mysql.connector

# Add project root to sys.path
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Import config after path setup
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME # noqa: E402


def initialize_database() -> None:
    """Connect to MySQL and execute the schema.sql file."""
    print("Attempting to connect to MySQL and initialize database...")
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
        )
        cursor = conn.cursor()

        schema_path = os.path.join(_ROOT, "app", "database", "schema.sql")
        with open(schema_path, "r") as f:
            sql_script = f.read()
        
        for statement in sql_script.split(';'):
            if statement.strip():
                cursor.execute(statement)
        conn.commit()
        print("Database schema initialized successfully!")

    except mysql.connector.Error as err:
        print(f"Error initializing database: {err}")
        sys.exit(1)
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()


if __name__ == "__main__":
    initialize_database()
