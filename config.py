import os

DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = ""
DB_NAME = "ai_tender_laws"



BASE_DIR = os.path.dirname(os.path.abspath(__file__))

VECTOR_DB_PATH = os.path.join(BASE_DIR, "data", "vector_db")
