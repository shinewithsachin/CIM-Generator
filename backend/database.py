"""
Lightweight SQLite store for users, session ownership, per-user LLM config,
audit events, and durable session state. No ORM — keeps it dependency-light
and fast; JSON columns are used for the free-form session blobs rather than
a fully normalized schema, which is a deliberate scope trade-off for a
project of this size.
"""
import json
import sqlite3
import os
from datetime import datetime, timedelta, timezone

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
                id              TEXT PRIMARY KEY,
                email           TEXT UNIQUE NOT NULL,
                name            TEXT NOT NULL,
                password        TEXT NOT NULL,
                failed_attempts INTEGER DEFAULT 0,
                locked_until    TEXT,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS session_owners (
                session_id  TEXT PRIMARY KEY,
                user_id     TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS user_llm_config (
                user_id             TEXT PRIMARY KEY,
                llm_provider        TEXT,
                llm_model           TEXT,
                openai_api_key_enc  TEXT,
                anthropic_api_key_enc TEXT,
                groq_api_key_enc    TEXT,
                openai_model        TEXT,
                anthropic_model     TEXT,
                groq_model          TEXT,
                embedding_model     TEXT,
                vector_backend      TEXT,
                postgres_dsn        TEXT,
                updated_at          TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT,
                action      TEXT NOT NULL,
                resource_id TEXT,
                ip_address  TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id                  TEXT PRIMARY KEY,
                owner_id            TEXT NOT NULL,
                status              TEXT NOT NULL,
                files_json          TEXT DEFAULT '[]',
                sections_json       TEXT DEFAULT '{}',
                processing_log_json TEXT DEFAULT '[]',
                chat_history_json   TEXT DEFAULT '[]',
                generation_progress_json TEXT DEFAULT '{}',
                pdf_status          TEXT,
                pdf_path            TEXT,
                pdf_password_enc    TEXT,
                created_at          TEXT DEFAULT (datetime('now')),
                updated_at          TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (owner_id) REFERENCES users(id)
            );
        """)
        # Lightweight migration for DBs created before these columns existed.
        existing_cols = {row["name"] for row in c.execute("PRAGMA table_info(users)")}
        if "failed_attempts" not in existing_cols:
            c.execute("ALTER TABLE users ADD COLUMN failed_attempts INTEGER DEFAULT 0")
        if "locked_until" not in existing_cols:
            c.execute("ALTER TABLE users ADD COLUMN locked_until TEXT")


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


# ── Login lockout ─────────────────────────────────────

def is_locked_out(user: dict) -> bool:
    locked_until = user.get("locked_until")
    if not locked_until:
        return False
    try:
        expires = datetime.fromisoformat(locked_until)
    except ValueError:
        return False
    return datetime.now(timezone.utc).replace(tzinfo=None) < expires


def record_failed_login(user_id: str, max_attempts: int, lockout_minutes: int):
    with _conn() as c:
        row = c.execute("SELECT failed_attempts FROM users WHERE id = ?", (user_id,)).fetchone()
        attempts = (row["failed_attempts"] or 0) + 1 if row else 1
        locked_until = None
        if attempts >= max_attempts:
            locked_until = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=lockout_minutes)).isoformat()
        c.execute(
            "UPDATE users SET failed_attempts = ?, locked_until = ? WHERE id = ?",
            (attempts, locked_until, user_id),
        )


def reset_failed_login(user_id: str):
    with _conn() as c:
        c.execute("UPDATE users SET failed_attempts = 0, locked_until = NULL WHERE id = ?", (user_id,))


# ── Per-user LLM config ────────────────────────────────

def get_user_llm_config_row(user_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM user_llm_config WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def upsert_user_llm_config(user_id: str, fields: dict):
    columns = list(fields.keys())
    with _conn() as c:
        existing = c.execute("SELECT user_id FROM user_llm_config WHERE user_id = ?", (user_id,)).fetchone()
        if existing:
            set_clause = ", ".join(f"{col} = ?" for col in columns)
            c.execute(
                f"UPDATE user_llm_config SET {set_clause}, updated_at = datetime('now') WHERE user_id = ?",
                (*fields.values(), user_id),
            )
        else:
            cols_sql = ", ".join(["user_id"] + columns)
            placeholders = ", ".join(["?"] * (len(columns) + 1))
            c.execute(
                f"INSERT INTO user_llm_config ({cols_sql}) VALUES ({placeholders})",
                (user_id, *fields.values()),
            )


# ── Audit log ──────────────────────────────────────────

def record_audit(user_id: str | None, action: str, resource_id: str | None = None, ip_address: str | None = None):
    with _conn() as c:
        c.execute(
            "INSERT INTO audit_log (user_id, action, resource_id, ip_address) VALUES (?, ?, ?, ?)",
            (user_id, action, resource_id, ip_address),
        )


def get_audit_events(user_id: str, limit: int = 100) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT action, resource_id, ip_address, created_at FROM audit_log "
            "WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Session persistence (write-through cache backing) ──

_SESSION_JSON_FIELDS = ("files", "sections", "processing_log", "chat_history", "generation_progress")


def save_session(session: dict):
    payload = {
        "id": session["id"],
        "owner_id": session["owner_id"],
        "status": session["status"],
        "files_json": json.dumps(session.get("files", [])),
        "sections_json": json.dumps(session.get("sections", {})),
        "processing_log_json": json.dumps(session.get("processing_log", [])),
        "chat_history_json": json.dumps(session.get("chat_history", [])),
        "generation_progress_json": json.dumps(session.get("generation_progress", {})),
        "pdf_status": session.get("pdf_status"),
        "pdf_path": session.get("pdf_path"),
        "pdf_password_enc": session.get("pdf_password_enc"),
    }
    with _conn() as c:
        existing = c.execute("SELECT id FROM sessions WHERE id = ?", (payload["id"],)).fetchone()
        if existing:
            c.execute(
                """UPDATE sessions SET owner_id=?, status=?, files_json=?, sections_json=?,
                   processing_log_json=?, chat_history_json=?, generation_progress_json=?,
                   pdf_status=?, pdf_path=?, pdf_password_enc=?, updated_at=datetime('now')
                   WHERE id=?""",
                (
                    payload["owner_id"], payload["status"], payload["files_json"], payload["sections_json"],
                    payload["processing_log_json"], payload["chat_history_json"], payload["generation_progress_json"],
                    payload["pdf_status"], payload["pdf_path"], payload["pdf_password_enc"], payload["id"],
                ),
            )
        else:
            c.execute(
                """INSERT INTO sessions (id, owner_id, status, files_json, sections_json,
                   processing_log_json, chat_history_json, generation_progress_json,
                   pdf_status, pdf_path, pdf_password_enc)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    payload["id"], payload["owner_id"], payload["status"], payload["files_json"], payload["sections_json"],
                    payload["processing_log_json"], payload["chat_history_json"], payload["generation_progress_json"],
                    payload["pdf_status"], payload["pdf_path"], payload["pdf_password_enc"],
                ),
            )


def load_session(session_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if not row:
        return None
    row = dict(row)
    return {
        "id": row["id"],
        "owner_id": row["owner_id"],
        "status": row["status"],
        "files": json.loads(row["files_json"] or "[]"),
        "sections": json.loads(row["sections_json"] or "{}"),
        "processing_log": json.loads(row["processing_log_json"] or "[]"),
        "chat_history": json.loads(row["chat_history_json"] or "[]"),
        "generation_progress": json.loads(row["generation_progress_json"] or "{}"),
        "pdf_status": row["pdf_status"],
        "pdf_path": row["pdf_path"],
        "pdf_password_enc": row["pdf_password_enc"],
    }


def delete_session_row(session_id: str):
    with _conn() as c:
        c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))


def get_expired_sessions(retention_days: int) -> list[dict]:
    cutoff = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=retention_days)).isoformat()
    with _conn() as c:
        rows = c.execute("SELECT id, owner_id, pdf_path FROM sessions WHERE created_at < ?", (cutoff,)).fetchall()
    return [dict(r) for r in rows]
