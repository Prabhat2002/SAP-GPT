# =====================================================
# FILE NAME : database.py
# CHANGE    : Switched from PostgreSQL (psycopg2) to
#             SQLite (built-in). No installation needed.
#             DB file "sapgpt.db" is auto-created next
#             to this file on first run.
# =====================================================

import sqlite3
import random
import string
import os

# =====================================================
# DB FILE PATH — always next to this script
# =====================================================

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, "sapgpt.db")


# =====================================================
# DATABASE CONNECTION
# =====================================================

def get_connection():
    # check_same_thread=False is required for Streamlit
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return conn


# =====================================================
# GENERATE TEAM CODE
# =====================================================

def generate_team_code():
    return ''.join(
        random.choices(
            string.ascii_uppercase + string.digits,
            k=6
        )
    )


# =====================================================
# INIT DATABASE
# =====================================================
# SQLite differences vs PostgreSQL:
#   SERIAL PRIMARY KEY  ->  INTEGER PRIMARY KEY AUTOINCREMENT
#   %s placeholders     ->  ? placeholders

def init_db():

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
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

    conn.commit()
    cur.close()
    conn.close()


# =====================================================
# SAVE ERROR
# =====================================================

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


# =====================================================
# FETCH USER HISTORY
# =====================================================

def fetch_user_history(user_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT * FROM saved_errors
        WHERE user_id = ?
        ORDER BY id DESC
    """, (str(user_id),))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# =====================================================
# DELETE ERROR
# =====================================================

def delete_error(error_id):

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM saved_errors WHERE id = ?", (error_id,))
    conn.commit()
    cur.close()
    conn.close()


# =====================================================
# CREATE TEAM
# =====================================================

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


# =====================================================
# FETCH USER TEAMS
# =====================================================

def fetch_user_teams(user_id):
    """Returns all teams the user created OR joined (approved)."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT DISTINCT t.team_name, t.team_code, t.created_by
        FROM teams t
        LEFT JOIN team_members tm ON tm.team_code = t.team_code
        WHERE t.created_by = ?
           OR tm.user_id = ?
        ORDER BY t.id DESC
    """, (str(user_id), str(user_id)))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# =====================================================
# SAVE TEAM DEFECT
# =====================================================

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


# =====================================================
# SEND JOIN REQUEST
# =====================================================

def send_join_request(team_code, user_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO join_requests (team_code, requested_user)
        VALUES (?, ?)
    """, (team_code, user_id))

    conn.commit()
    cur.close()
    conn.close()


# =====================================================
# FETCH JOIN REQUESTS (for team owner)
# =====================================================

def fetch_join_requests(owner_id):
    """Returns pending requests for teams owned by owner_id.
       Shows username instead of raw user_id number."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT jr.id,
               jr.team_code,
               jr.requested_user,
               COALESCE(u.username, jr.requested_user) AS display_name,
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


# =====================================================
# APPROVE REQUEST
# =====================================================

def approve_request(request_id, team_code, user_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO team_members (team_code, user_id)
        VALUES (?, ?)
    """, (team_code, user_id))

    cur.execute("DELETE FROM join_requests WHERE id = ?", (request_id,))

    conn.commit()
    cur.close()
    conn.close()


# =====================================================
# REJECT REQUEST
# =====================================================

def reject_request(request_id):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("DELETE FROM join_requests WHERE id = ?", (request_id,))

    conn.commit()
    cur.close()
    conn.close()


# =====================================================
# FETCH TEAM MEMBERS
# =====================================================

def fetch_team_members(team_code):
    """Returns all members including the creator (who is never in team_members table).
    Creator always appears first with role tag, rest are members."""

    conn = get_connection()
    cur = conn.cursor()

    # Get creator first (stored in teams table, NOT in team_members)
    cur.execute("""
        SELECT t.created_by, COALESCE(u.username, t.created_by), 'owner'
        FROM teams t
        LEFT JOIN users u ON u.id = CAST(t.created_by AS INTEGER)
        WHERE t.team_code = ?
    """, (team_code,))
    creator = cur.fetchone()

    # Get approved members (stored in team_members table)
    cur.execute("""
        SELECT tm.user_id, COALESCE(u.username, tm.user_id), 'member'
        FROM team_members tm
        LEFT JOIN users u ON u.id = CAST(tm.user_id AS INTEGER)
        WHERE tm.team_code = ?
    """, (team_code,))
    members = cur.fetchall()

    cur.close()
    conn.close()

    # Combine: creator first, then members (deduplicate in case creator also joined)
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


# =====================================================
# FETCH TEAM DEFECTS
# =====================================================

def fetch_team_defects(team_code):

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, team_name, error_text, analysis, created_by
        FROM team_defects
        WHERE team_code = ?
        ORDER BY id DESC
    """, (team_code,))

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# =====================================================
# SEARCH SIMILAR TEAM DEFECTS (duplicate detection)
# =====================================================

def search_similar_team_defects(team_code, error_keywords, limit=3):
    """Find existing team defects that share keywords with the new error.
    Returns up to `limit` matches ordered by most recent."""
    conn = get_connection()
    cur = conn.cursor()

    # Build a simple keyword match — check each word individually
    words = [w.strip() for w in error_keywords.split() if len(w.strip()) > 4][:6]

    if not words:
        conn.close()
        return []

    like_clauses = " OR ".join(["LOWER(error_text) LIKE ?"] * len(words))
    params = [f"%{w.lower()}%" for w in words] + [team_code]

    cur.execute(f"""
        SELECT id, error_text, analysis, created_by
        FROM team_defects
        WHERE ({like_clauses})
          AND team_code = ?
        ORDER BY id DESC
        LIMIT ?
    """, params + [limit])

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# =====================================================
# DELETE TEAM (creator only — cascades to all members/defects/requests)
# =====================================================

def delete_team(team_code, user_id):
    """Delete team and all associated data. Only creator can delete."""
    conn = get_connection()
    cur = conn.cursor()

    # Verify ownership first
    cur.execute("SELECT created_by FROM teams WHERE team_code = ?", (team_code,))
    row = cur.fetchone()
    if not row or str(row[0]) != str(user_id):
        cur.close()
        conn.close()
        return False  # not owner

    # Cascade delete everything related to this team
    for table in ("team_members", "team_defects", "join_requests"):
        cur.execute(f"DELETE FROM {table} WHERE team_code = ?", (team_code,))

    cur.execute("DELETE FROM teams WHERE team_code = ?", (team_code,))

    conn.commit()
    cur.close()
    conn.close()
    return True


# =====================================================
# LEAVE TEAM (member only)
# =====================================================

def leave_team(team_code, user_id):
    """Remove a member from a team. Creator cannot leave (must delete)."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM team_members WHERE team_code = ? AND user_id = ?",
        (team_code, str(user_id))
    )

    conn.commit()
    cur.close()
    conn.close()


# =====================================================
# FEEDBACK / RATING SYSTEM
# =====================================================

def save_feedback(user_id, platform, error_text, analysis, rating, comment=""):
    conn = get_connection()
    cur = conn.cursor()
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
        )
    """)
    cur.execute("""
        INSERT INTO feedback (user_id, platform, error_text, analysis, rating, comment)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (str(user_id), platform, error_text, analysis, rating, comment))
    conn.commit()
    cur.close()
    conn.close()


def fetch_feedback_examples(platform, rating="useful", limit=5):
    """Fetch highly-rated Q&A pairs to use as few-shot examples."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, platform TEXT,
            error_text TEXT, analysis TEXT,
            rating TEXT, comment TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        SELECT error_text, analysis
        FROM feedback
        WHERE platform = ? AND rating = ?
        ORDER BY id DESC LIMIT ?
    """, (platform, rating, limit))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


# =====================================================
# PENDING REQUEST COUNT (for sidebar badge)
# =====================================================

def count_pending_requests(owner_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*)
        FROM join_requests jr
        INNER JOIN teams t ON jr.team_code = t.team_code
        WHERE t.created_by = ?
    """, (str(owner_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else 0


# =====================================================
# GET USERNAME BY ID
# =====================================================

def get_username(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT username FROM users WHERE id = ?", (int(user_id),))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row[0] if row else f"User #{user_id}"


# =====================================================
# FETCH USER FEEDBACK STATS
# =====================================================

def fetch_user_feedback_stats(user_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT, platform TEXT,
            error_text TEXT, analysis TEXT,
            rating TEXT, comment TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        SELECT rating, COUNT(*) FROM feedback
        WHERE user_id = ?
        GROUP BY rating
    """, (str(user_id),))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return {r[0]: r[1] for r in rows}
