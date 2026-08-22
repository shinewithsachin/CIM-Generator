"""
Lightweight SQLite store for users and session ownership.
No ORM — keeps it dependency-light and fast.
"""
import sqlite3
import os
from pathlib import Path

DB_PATH = os.environ.get("DB_PATH", "./cim_users.db")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    with _conn() as c:
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id          TEXT PRIMARY KEY,
                email       TEXT UNIQUE NOT NULL,
                name        TEXT NOT NULL,
                password    TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS session_owners (
                session_id  TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)


# ── Users ─────────────────────────────────────────────

def create_user(user_id: str, email: str, name: str, hashed_password: str) -> dict:
    with _conn() as c:
        c.execute(
            "INSERT INTO users (id, email, name, password) VALUES (?, ?, ?, ?)",
            (user_id, email.lower().strip(), name.strip(), hashed_password)
        )
    return {"id": user_id, "email": email, "name": name}


def get_user_by_email(email: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),)).fetchone()
    return dict(row) if row else None


def get_user_by_id(user_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


# ── Session ownership ─────────────────────────────────

def bind_session_to_user(session_id: str, user_id: str):
    with _conn() as c:
        c.execute(
            "INSERT OR IGNORE INTO session_owners (session_id, user_id) VALUES (?, ?)",
            (session_id, user_id)
        )


def get_session_owner(session_id: str) -> str | None:
    with _conn() as c:
        row = c.execute(
            "SELECT user_id FROM session_owners WHERE session_id = ?", (session_id,)
        ).fetchone()
    return row["user_id"] if row else None


def get_user_sessions(user_id: str) -> list[str]:
    with _conn() as c:
        rows = c.execute(
            "SELECT session_id FROM session_owners WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
    return [r["session_id"] for r in rows]


def delete_session_ownership(session_id: str):
    with _conn() as c:
        c.execute("DELETE FROM session_owners WHERE session_id = ?", (session_id,))
