import json
import sqlite3
from typing import Any

from app.repositories.database import Database


class WorkshopRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_user_if_absent(
        self,
        username: str,
        password_hash: str,
        salt: str,
        display_name: str,
        role: str,
        created_at: str,
    ) -> None:
        with self.database.connect() as connection:
            exists = connection.execute(
                "SELECT 1 FROM users WHERE username = ?", (username,)
            ).fetchone()
            if exists:
                return
            connection.execute(
                """
                INSERT INTO users
                    (username, password_hash, salt, display_name, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (username, password_hash, salt, display_name, role, created_at),
            )

    def create_user(
        self,
        username: str,
        password_hash: str,
        salt: str,
        display_name: str,
        created_at: str,
    ) -> sqlite3.Row:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO users
                    (username, password_hash, salt, display_name, role, created_at)
                VALUES (?, ?, ?, ?, 'user', ?)
                """,
                (username, password_hash, salt, display_name, created_at),
            )
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
        if row is None:
            raise RuntimeError("User creation did not return a row")
        return row

    def find_active_user_by_username(self, username: str) -> sqlite3.Row | None:
        with self.database.connect() as connection:
            return connection.execute(
                "SELECT * FROM users WHERE username = ? AND is_active = 1",
                (username,),
            ).fetchone()

    def create_session(
        self, token: str, user_id: int, created_at: str, expires_at: str
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions (token, user_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (token, user_id, created_at, expires_at),
            )

    def delete_session(self, token: str) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token = ?", (token,))

    def delete_expired_sessions(self, now: str) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))

    def find_user_by_session(self, token: str, now: str) -> sqlite3.Row | None:
        with self.database.connect() as connection:
            return connection.execute(
                """
                SELECT u.* FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token = ? AND s.expires_at > ? AND u.is_active = 1
                """,
                (token, now),
            ).fetchone()

    def record_activity(
        self,
        user_id: int,
        feature: str,
        input_preview: str,
        output_preview: str,
        status: str,
        duration_ms: int,
        created_at: str,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO activity_logs
                    (user_id, feature, input_preview, output_preview, status, error,
                     duration_ms, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    feature,
                    input_preview[:500],
                    output_preview[:500],
                    status,
                    error[:500] if error else None,
                    duration_ms,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    created_at,
                ),
            )

    def list_admin_users(self) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT u.id, u.username, u.display_name, u.role, u.created_at,
                       COUNT(a.id) AS request_count,
                       SUM(CASE WHEN a.status = 'success' THEN 1 ELSE 0 END) AS success_count,
                       SUM(CASE WHEN a.status = 'error' THEN 1 ELSE 0 END) AS error_count,
                       MAX(a.created_at) AS last_active_at
                FROM users u
                LEFT JOIN activity_logs a ON a.user_id = u.id
                GROUP BY u.id
                ORDER BY request_count DESC, u.id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_activity_logs(self, limit: int) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT a.id, u.username, u.display_name, a.feature, a.status,
                       a.duration_ms, a.input_preview, a.error, a.created_at
                FROM activity_logs a
                JOIN users u ON u.id = a.user_id
                ORDER BY a.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]
