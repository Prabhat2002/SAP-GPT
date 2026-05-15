from database import get_connection


def register_user(username, password):

    conn = get_connection()
    cur = conn.cursor()

    # FIX: SQLite uses ? placeholders, not %s
    cur.execute(
        "SELECT * FROM users WHERE username = ?",
        (username,)
    )

    existing = cur.fetchone()

    if existing:
        cur.close()
        conn.close()
        return False

    cur.execute(
        "INSERT INTO users (username, password) VALUES (?, ?)",
        (username, password)
    )

    conn.commit()
    cur.close()
    conn.close()

    return True


def login_user(username, password):

    conn = get_connection()
    cur = conn.cursor()

    # FIX: SQLite uses ? placeholders, not %s
    cur.execute(
        "SELECT id FROM users WHERE username = ? AND password = ?",
        (username, password)
    )

    row = cur.fetchone()

    cur.close()
    conn.close()

    if row:
        return row[0]

    return None
