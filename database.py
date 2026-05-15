import sqlite3
import random
import string
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, "sapgpt.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn


def generate_team_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        email    TEXT UNIQUE,
        password TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS otp_store (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        email      TEXT,
        otp        TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS saved_errors (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id    TEXT,
        platform   TEXT,
        error_text TEXT,
        analysis   TEXT,
        severity   TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        team_name    TEXT,
        project_name TEXT,
        team_code    TEXT,
        created_by   TEXT,
        notes        TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS team_defects (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        team_code  TEXT,
        team_name  TEXT,
        error_text TEXT,
        analysis   TEXT,
        created_by TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS join_requests (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        team_code      TEXT,
        requested_user TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS team_members (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        team_code TEXT,
        user_id   TEXT
    )""")

    cur.execute("""
    CREATE TABLE IF NOT EXISTS feedback (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     TEXT,
        platform    TEXT,
        error_text  TEXT,
        analysis    TEXT,
        rating      TEXT,
        comment     TEXT,
        created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")

    try:
        cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
    except Exception:
        pass

    conn.commit()
    cur.close()
    conn.close()


def save_otp(email, otp):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM otp_store WHERE email = ?", (email.lower(),))
    cur.execute("INSERT INTO otp_store (email, otp) VALUES (?, ?)", (email.lower(), otp))
    conn.commit()
    cur.close()
    conn.close()


def verify_otp(email, otp):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id FROM otp_store
        WHERE email = ? AND otp = ?
        AND created_at >= datetime('now', '-10 minutes')
    """, (email.lower(), otp))
    row = cur.fetchone()
    if row:
        cur.execute("DELETE FROM otp_store WHERE email = ?", (email.lower(),))
    conn.commit()
    cur.close()
    conn.close()
    return row is not None


def email_exists(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = ?", (email.lower(),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row is not None


def register_user_email(email, password=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = ?", (email.lower(),))
    if cur.fetchone():
        cur.close()
        conn.close()
        return False
    username = email.split("@")[0]
    cur.execute(
        "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
        (username, email.lower(), password or "")
    )
    conn.commit()
    cur.close()
    conn.close()
    return True


def login_user_email(email, password):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM users WHERE email = ? AND password = ?",
        (email.lower(), password)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else None


def login_user_otp(email):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE email = ?", (email.lower(),))
    row = cur.fetchone()
    if row:
        cur.close()
        conn.close()
        return row[0]
    username = email.split("@")[0]
    cur.execute(
        "INSERT INTO users (username, email, password) VALUES (?, ?, ?)",
        (username, email.lower(), "")
    )
    conn.commit()
    user_id = cur.lastrowid
    cur.close()
    conn.close()
    return user_id


def save_error(user_id, platform, error_text, analysis, severity):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO saved_errors (user_id, platform, error_text, analysis, severity)
        VALUES (?, ?, ?, ?, ?)
    """, (str(user_id), platform, error_text, analysis, severity))
    conn.commit()
    cur.close()
    conn.close()


def fetch_user_history(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT * FROM saved_errors WHERE user_id = ? ORDER BY id DESC
    """, (str(user_id),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def delete_error(error_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM saved_errors WHERE id = ?", (error_id,))
    conn.commit()
    cur.close()
    conn.close()


def create_team(team_name, project_name, created_by, notes):
    conn = get_connection()
    cur = conn.cursor()
    team_code = generate_team_code()
    cur.execute("""
        INSERT INTO teams (team_name, project_name, team_code, created_by, notes)
        VALUES (?, ?, ?, ?, ?)
    """, (team_name, project_name, team_code, created_by, notes))
    conn.commit()
    cur.close()
    conn.close()
    return team_code


def fetch_user_teams(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT t.team_name, t.team_code, t.created_by
        FROM teams t
        LEFT JOIN team_members tm ON tm.team_code = t.team_code
        WHERE t.created_by = ? OR tm.user_id = ?
        ORDER BY t.id DESC
    """, (str(user_id), str(user_id)))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def save_team_defect(team_code, team_name, error_text, analysis, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO team_defects (team_code, team_name, error_text, analysis, created_by)
        VALUES (?, ?, ?, ?, ?)
    """, (team_code, team_name, error_text, analysis, user_id))
    conn.commit()
    cur.close()
    conn.close()


def send_join_request(team_code, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO join_requests (team_code, requested_user) VALUES (?, ?)", (team_code, user_id))
    conn.commit()
    cur.close()
    conn.close()


def fetch_join_requests(owner_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT jr.id, jr.team_code, jr.requested_user,
               COALESCE(u.username, u.email, jr.requested_user) AS display_name,
               t.team_name
        FROM join_requests jr
        INNER JOIN teams t ON jr.team_code = t.team_code
        LEFT JOIN users u ON u.id = CAST(jr.requested_user AS INTEGER)
        WHERE t.created_by = ?
    """, (str(owner_id),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def approve_request(request_id, team_code, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO team_members (team_code, user_id) VALUES (?, ?)", (team_code, user_id))
    cur.execute("DELETE FROM join_requests WHERE id = ?", (request_id,))
    conn.commit()
    cur.close()
    conn.close()


def reject_request(request_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM join_requests WHERE id = ?", (request_id,))
    conn.commit()
    cur.close()
    conn.close()


def fetch_team_members(team_code):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT t.created_by, COALESCE(u.username, u.email, t.created_by), 'owner'
        FROM teams t
        LEFT JOIN users u ON u.id = CAST(t.created_by AS INTEGER)
        WHERE t.team_code = ?
    """, (team_code,))
    creator = cur.fetchone()
    cur.execute("""
        SELECT tm.user_id, COALESCE(u.username, u.email, tm.user_id), 'member'
        FROM team_members tm
        LEFT JOIN users u ON u.id = CAST(tm.user_id AS INTEGER)
        WHERE tm.team_code = ?
    """, (team_code,))
    members = cur.fetchall()
    cur.close()
    conn.close()
    all_members = []
    seen = set()
    if creator:
        all_members.append(creator)
        seen.add(str(creator[0]))
    for m in members:
        if str(m[0]) not in seen:
            all_members.append(m)
            seen.add(str(m[0]))
    return all_members


def fetch_team_defects(team_code):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, team_name, error_text, analysis, created_by
        FROM team_defects WHERE team_code = ? ORDER BY id DESC
    """, (team_code,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def search_similar_team_defects(team_code, error_keywords, limit=3):
    conn = get_connection()
    cur = conn.cursor()
    words = [w.strip() for w in error_keywords.split() if len(w.strip()) > 4][:6]
    if not words:
        conn.close()
        return []
    like_clauses = " OR ".join(["LOWER(error_text) LIKE ?"] * len(words))
    params = [f"%{w.lower()}%" for w in words] + [team_code]
    cur.execute(f"""
        SELECT id, error_text, analysis, created_by
        FROM team_defects WHERE ({like_clauses}) AND team_code = ?
        ORDER BY id DESC LIMIT ?
    """, params + [limit])
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def delete_team(team_code, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT created_by FROM teams WHERE team_code = ?", (team_code,))
    row = cur.fetchone()
    if not row or str(row[0]) != str(user_id):
        cur.close()
        conn.close()
        return False
    for table in ("team_members", "team_defects", "join_requests"):
        cur.execute(f"DELETE FROM {table} WHERE team_code = ?", (team_code,))
    cur.execute("DELETE FROM teams WHERE team_code = ?", (team_code,))
    conn.commit()
    cur.close()
    conn.close()
    return True


def leave_team(team_code, user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM team_members WHERE team_code = ? AND user_id = ?", (team_code, str(user_id)))
    conn.commit()
    cur.close()
    conn.close()


def save_feedback(user_id, platform, error_text, analysis, rating, comment=""):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO feedback (user_id, platform, error_text, analysis, rating, comment)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (str(user_id), platform, error_text, analysis, rating, comment))
    conn.commit()
    cur.close()
    conn.close()


def fetch_feedback_examples(platform, rating="useful", limit=5):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT error_text, analysis FROM feedback
        WHERE platform = ? AND rating = ? ORDER BY id DESC LIMIT ?
    """, (platform, rating, limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def count_pending_requests(owner_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM join_requests jr
        INNER JOIN teams t ON jr.team_code = t.team_code
        WHERE t.created_by = ?
    """, (str(owner_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else 0


def get_username(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(username, email) FROM users WHERE id = ?", (int(user_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else f"User #{user_id}"


def fetch_user_feedback_stats(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT rating, COUNT(*) FROM feedback WHERE user_id = ? GROUP BY rating", (str(user_id),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {r[0]: r[1] for r in rows}
