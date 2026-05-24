from app.database.db_connection import connect_db


def get_laws():
    conn = connect_db()

    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            id,
            link,
            title,
            law_type,
            law_number,
            law_date,
            content
        FROM laws
    """)

    laws = cursor.fetchall()

    for law in laws:
        law["title"] = str(law["title"]) if law["title"] else ""
        law["law_type"] = str(law["law_type"]) if law["law_type"] else ""
        law["law_number"] = str(law["law_number"]) if law["law_number"] else ""
        law["law_date"] = str(law["law_date"]) if law["law_date"] else ""
        law["content"] = str(law["content"]) if law["content"] else ""
        law["link"] = str(law["link"]) if law["link"] else ""

    conn.close()

    return laws