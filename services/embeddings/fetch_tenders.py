from app.database.db_connection import connect_db


def get_tenders():
    conn = connect_db()

    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT
            id,
            link,
            title,
            summary,
            final_submission_deadline,
            opening_session_date,
            document_location
        FROM tenders
    """)

    tenders = cursor.fetchall()

    for t in tenders:
        t["final_submission_deadline"] = str(t["final_submission_deadline"]) if t["final_submission_deadline"] else ""
        t["opening_session_date"] = str(t["opening_session_date"]) if t["opening_session_date"] else ""
        t["title"] = str(t["title"]) if t["title"] else ""
        t["summary"] = str(t["summary"]) if t["summary"] else ""
        t["document_location"] = str(t["document_location"]) if t["document_location"] else ""
        t["link"] = str(t["link"]) if t["link"] else ""

    conn.close()

    return tenders