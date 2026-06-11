import mysql.connector
from mysql.connector import Error
import os
import time

def connect_db(retries=3, delay=2):
    """
    Connects to the MySQL database with retry logic.
    - retries: Number of times to attempt connection if it fails.
    - delay: Seconds to wait between retries.
    """
    for attempt in range(retries):
        try:
            # Use Environment Variables from Railway
            connection = mysql.connector.connect(
                host=os.getenv("DB_HOST", "localhost"),
                user=os.getenv("DB_USER", "root"),
                password=os.getenv("DB_PASSWORD", ""),
                database=os.getenv("DB_NAME", "railway"),
                port=int(os.getenv("DB_PORT", "3306")),
                # CRITICAL: Stability settings for Cloud
                connection_timeout=15, # Stop waiting after 15 seconds
                buffered=True,         # Keeps results in memory to avoid "stale" errors
                autocommit=True        # Ensures data is saved immediately
            )

            if connection.is_connected():
                return connection

        except Error as e:
            print(f"❌ Connection attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                print(f"⏳ Retrying in {delay} seconds...")
                time.sleep(delay)
            else:
                print("🚨 All database connection attempts failed.")
                # We return None instead of crashing the whole app
                return None

    return None