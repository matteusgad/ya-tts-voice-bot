import os
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any


DB_FILENAME = 'voicebot.sqlite3'


def get_db_path(base_dir: str) -> str:
    return os.path.join(base_dir, DB_FILENAME)


def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            is_admin INTEGER DEFAULT 0,
            status TEXT DEFAULT 'approved', -- 'approved' | 'pending' | 'denied'
            created_at TEXT
        );
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER PRIMARY KEY,
            voice TEXT,
            speed REAL,
            emotion TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
        );
        """
    )
    conn.commit()


def upsert_user(conn: sqlite3.Connection, user_id: int, username: Optional[str], *, is_admin: bool = False, status: Optional[str] = None) -> None:
    cursor = conn.cursor()
    # Check existence
    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    now = datetime.utcnow().isoformat()
    if row is None:
        cursor.execute(
            "INSERT INTO users (user_id, username, is_admin, status, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, username, int(is_admin), status or 'approved', now),
        )
    else:
        # Update username and optionally is_admin/status
        if status is None:
            cursor.execute(
                "UPDATE users SET username = ?, is_admin = MAX(is_admin, ? ) WHERE user_id = ?",
                (username, int(is_admin), user_id),
            )
        else:
            cursor.execute(
                "UPDATE users SET username = ?, is_admin = MAX(is_admin, ?), status = ? WHERE user_id = ?",
                (username, int(is_admin), status, user_id),
            )
    conn.commit()


def set_user_status(conn: sqlite3.Connection, user_id: int, status: str) -> None:
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
    conn.commit()


def set_admin(conn: sqlite3.Connection, user_id: int, is_admin: bool) -> None:
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_admin = ? WHERE user_id = ?", (int(is_admin), user_id))
    conn.commit()


def get_user(conn: sqlite3.Connection, user_id: int) -> Optional[Dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_admin_ids(conn: sqlite3.Connection) -> List[int]:
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users WHERE is_admin = 1")
    return [r[0] for r in cursor.fetchall()]


def get_settings(conn: sqlite3.Connection, user_id: int, *, default_voice: str, default_speed: float, default_emotion: str) -> Dict[str, Any]:
    cursor = conn.cursor()
    cursor.execute("SELECT voice, speed, emotion FROM settings WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    if row:
        return {
            'voice': row[0] or default_voice,
            'speed': float(row[1]) if row[1] is not None else default_speed,
            'emotion': row[2] or default_emotion,
        }
    return {'voice': default_voice, 'speed': float(default_speed), 'emotion': default_emotion}


def update_settings(conn: sqlite3.Connection, user_id: int, *, voice: Optional[str] = None, speed: Optional[float] = None, emotion: Optional[str] = None) -> None:
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM settings WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone() is not None
    if not exists:
        cursor.execute("INSERT INTO settings (user_id, voice, speed, emotion) VALUES (?, ?, ?, ?)", (user_id, voice, speed, emotion))
    else:
        # Build dynamic update
        parts = []
        values: List[object] = []
        if voice is not None:
            parts.append("voice = ?")
            values.append(voice)
        if speed is not None:
            parts.append("speed = ?")
            values.append(speed)
        if emotion is not None:
            parts.append("emotion = ?")
            values.append(emotion)
        if parts:
            values.append(user_id)
            cursor.execute(f"UPDATE settings SET {', '.join(parts)} WHERE user_id = ?", values)
    conn.commit()


def seed_from_users_allow(conn: sqlite3.Connection, base_dir: str) -> None:
    allow_path = os.path.join(base_dir, 'users.allow')
    if not os.path.exists(allow_path):
        return
    with open(allow_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]
    for line in lines:
        is_admin = False
        content = line
        # Formats supported:
        #   admin:123456789
        #   admin:@username or admin:username
        #   123456789 or @username or username (approved user)
        if line.lower().startswith('admin:'):
            is_admin = True
            content = line.split(':', 1)[1].strip()
        # Extract ID if numeric, else keep username
        user_id = None
        username = None
        if content.isdigit():
            user_id = int(content)
        else:
            username = content.lstrip('@')
        # Only insert numeric IDs now; username-only lines are applied when the user appears at runtime
        if user_id is not None:
            upsert_user(conn, user_id, username=None, is_admin=is_admin, status='approved')


