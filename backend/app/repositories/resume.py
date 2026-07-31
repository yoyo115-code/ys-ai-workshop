import hashlib
import json
from typing import Any

from app.repositories.database import Database


class ResumeConflictError(Exception):
    pass


class SuggestionStateError(Exception):
    pass


class VersionCreationError(Exception):
    pass


class ResumeRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def ensure_resume(
        self,
        user_id: int,
        application_id: int,
        name: str,
        content: str,
        created_at: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            resume = connection.execute(
                """
                SELECT * FROM resumes
                WHERE user_id = ? AND source_application_id = ? AND deleted_at IS NULL
                """,
                (user_id, application_id),
            ).fetchone()
            if resume is None:
                cursor = connection.execute(
                    """
                    INSERT INTO resumes
                        (user_id, name, source_application_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, name, application_id, created_at, created_at),
                )
                resume_id = int(cursor.lastrowid or 0)
                version_cursor = connection.execute(
                    """
                    INSERT INTO resume_versions
                        (resume_id, parent_version_id, version_number, source_type,
                         content, content_hash, created_at)
                    VALUES (?, NULL, 1, 'parsed', ?, ?, ?)
                    """,
                    (resume_id, content, self._hash(content), created_at),
                )
                version_id = int(version_cursor.lastrowid or 0)
                connection.execute(
                    "UPDATE resumes SET current_version_id = ? WHERE id = ?",
                    (version_id, resume_id),
                )
                resume = connection.execute(
                    "SELECT * FROM resumes WHERE id = ?", (resume_id,)
                ).fetchone()
            version = connection.execute(
                "SELECT * FROM resume_versions WHERE id = ?",
                (resume["current_version_id"],),
            ).fetchone()
        if resume is None or version is None:
            raise RuntimeError("Resume initialization failed")
        return dict(resume), dict(version)

    def get_resume_for_application(
        self, user_id: int, application_id: int
    ) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT r.* FROM resumes r
                JOIN job_applications a ON a.id = r.source_application_id
                WHERE r.source_application_id = ? AND r.user_id = ?
                  AND a.user_id = ? AND r.deleted_at IS NULL
                """,
                (application_id, user_id, user_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_version(self, version_id: int, user_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT v.* FROM resume_versions v
                JOIN resumes r ON r.id = v.resume_id
                WHERE v.id = ? AND r.user_id = ? AND r.deleted_at IS NULL
                """,
                (version_id, user_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_versions(self, resume_id: int, user_id: int) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT v.* FROM resume_versions v
                JOIN resumes r ON r.id = v.resume_id
                WHERE v.resume_id = ? AND r.user_id = ? AND r.deleted_at IS NULL
                ORDER BY v.version_number DESC, v.id DESC
                """,
                (resume_id, user_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_resume(self, resume_id: int, user_id: int) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM resumes WHERE id = ? AND user_id = ?",
                (resume_id, user_id),
            )
        return cursor.rowcount == 1

    def list_suggestions(
        self, application_id: int, version_id: int, user_id: int
    ) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT s.* FROM resume_suggestions s
                JOIN job_applications a ON a.id = s.application_id
                WHERE s.application_id = ? AND s.resume_version_id = ?
                  AND a.user_id = ?
                ORDER BY s.id ASC
                """,
                (application_id, version_id, user_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def active_suggestions(
        self, application_id: int, version_id: int, user_id: int
    ) -> list[dict[str, Any]]:
        return [
            row
            for row in self.list_suggestions(application_id, version_id, user_id)
            if row["status"] != "superseded"
        ]

    def create_suggestions(
        self,
        application_id: int,
        version_id: int,
        user_id: int,
        suggestions: list[dict[str, Any]],
        prompt_version: str,
        created_at: str,
        replace_active: bool,
    ) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            owned = connection.execute(
                "SELECT 1 FROM job_applications WHERE id = ? AND user_id = ?",
                (application_id, user_id),
            ).fetchone()
            if owned is None:
                raise ResumeConflictError("Application not found")
            current_generation = connection.execute(
                """
                SELECT COALESCE(MAX(generation_number), 0)
                FROM resume_suggestions
                WHERE application_id = ? AND resume_version_id = ?
                """,
                (application_id, version_id),
            ).fetchone()[0]
            generation = int(current_generation) + 1
            if replace_active:
                rows = connection.execute(
                    """
                    SELECT id, status FROM resume_suggestions
                    WHERE application_id = ? AND resume_version_id = ?
                      AND status != 'superseded'
                    """,
                    (application_id, version_id),
                ).fetchall()
                for row in rows:
                    connection.execute(
                        "UPDATE resume_suggestions SET status = 'superseded', decided_at = ? WHERE id = ?",
                        (created_at, row["id"]),
                    )
                    self._event(
                        connection,
                        row["id"],
                        "superseded",
                        {"status": row["status"]},
                        {"status": "superseded"},
                        created_at,
                    )
            ids: list[int] = []
            for suggestion in suggestions:
                cursor = connection.execute(
                    """
                    INSERT INTO resume_suggestions
                        (application_id, resume_version_id, section_key, source_text,
                         suggested_text, reason, jd_evidence, resume_evidence,
                         risk_level, clarification_required, status,
                         generation_number, prompt_version, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                    """,
                    (
                        application_id,
                        version_id,
                        suggestion["section_key"],
                        suggestion["source_text"],
                        suggestion["suggested_text"],
                        suggestion["reason"],
                        suggestion["jd_evidence"],
                        suggestion["resume_evidence"],
                        suggestion["risk_level"],
                        int(suggestion["clarification_required"]),
                        generation,
                        prompt_version,
                        created_at,
                    ),
                )
                suggestion_id = int(cursor.lastrowid or 0)
                ids.append(suggestion_id)
                self._event(
                    connection,
                    suggestion_id,
                    "generated",
                    {},
                    {"status": "pending", "generation_number": generation},
                    created_at,
                )
            placeholders = ",".join("?" for _ in ids)
            rows = connection.execute(
                f"SELECT * FROM resume_suggestions WHERE id IN ({placeholders}) ORDER BY id",
                ids,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_suggestion(self, suggestion_id: int, user_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT s.* FROM resume_suggestions s
                JOIN job_applications a ON a.id = s.application_id
                WHERE s.id = ? AND a.user_id = ?
                """,
                (suggestion_id, user_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def update_suggestion(
        self,
        suggestion_id: int,
        user_id: int,
        target_status: str,
        decided_at: str,
        suggested_text: str | None = None,
    ) -> dict[str, Any]:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                """
                SELECT s.* FROM resume_suggestions s
                JOIN job_applications a ON a.id = s.application_id
                WHERE s.id = ? AND a.user_id = ?
                """,
                (suggestion_id, user_id),
            ).fetchone()
            if row is None:
                raise ResumeConflictError("Suggestion not found")
            current_status = row["status"]
            if current_status == "superseded":
                raise SuggestionStateError("Superseded suggestions cannot be changed")
            if target_status in {"accepted", "rejected"}:
                if current_status == target_status:
                    return dict(row)
                if current_status != "pending":
                    raise SuggestionStateError("Illegal suggestion status transition")
            elif target_status == "edited":
                if current_status not in {"pending", "edited"}:
                    raise SuggestionStateError("Illegal suggestion status transition")
                if not suggested_text or not suggested_text.strip():
                    raise SuggestionStateError("Edited suggestion text is required")
            else:
                raise SuggestionStateError("Unsupported suggestion status")

            previous = {
                "status": current_status,
                "suggested_text": row["suggested_text"],
                "clarification_required": bool(row["clarification_required"]),
            }
            next_text = suggested_text.strip() if suggested_text else row["suggested_text"]
            next_clarification = 0 if target_status == "edited" else row["clarification_required"]
            connection.execute(
                """
                UPDATE resume_suggestions
                SET status = ?, suggested_text = ?, clarification_required = ?, decided_at = ?
                WHERE id = ?
                """,
                (
                    target_status,
                    next_text,
                    next_clarification,
                    decided_at,
                    suggestion_id,
                ),
            )
            self._event(
                connection,
                suggestion_id,
                target_status,
                previous,
                {
                    "status": target_status,
                    "suggested_text": next_text,
                    "clarification_required": bool(next_clarification),
                },
                decided_at,
            )
            updated = connection.execute(
                "SELECT * FROM resume_suggestions WHERE id = ?", (suggestion_id,)
            ).fetchone()
        if updated is None:
            raise RuntimeError("Suggestion update failed")
        return dict(updated)

    def replace_suggestion(
        self,
        old_suggestion_id: int,
        user_id: int,
        suggestion: dict[str, Any],
        prompt_version: str,
        created_at: str,
    ) -> dict[str, Any]:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            old = connection.execute(
                """
                SELECT s.* FROM resume_suggestions s
                JOIN job_applications a ON a.id = s.application_id
                WHERE s.id = ? AND a.user_id = ?
                """,
                (old_suggestion_id, user_id),
            ).fetchone()
            if old is None:
                raise ResumeConflictError("Suggestion not found")
            if old["status"] == "superseded":
                raise SuggestionStateError("Suggestion is already superseded")
            connection.execute(
                "UPDATE resume_suggestions SET status = 'superseded', decided_at = ? WHERE id = ?",
                (created_at, old_suggestion_id),
            )
            self._event(
                connection,
                old_suggestion_id,
                "superseded",
                {"status": old["status"]},
                {"status": "superseded"},
                created_at,
            )
            cursor = connection.execute(
                """
                INSERT INTO resume_suggestions
                    (application_id, resume_version_id, section_key, source_text,
                     suggested_text, reason, jd_evidence, resume_evidence,
                     risk_level, clarification_required, status,
                     generation_number, prompt_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    old["application_id"],
                    old["resume_version_id"],
                    suggestion["section_key"],
                    suggestion["source_text"],
                    suggestion["suggested_text"],
                    suggestion["reason"],
                    suggestion["jd_evidence"],
                    suggestion["resume_evidence"],
                    suggestion["risk_level"],
                    int(suggestion["clarification_required"]),
                    old["generation_number"] + 1,
                    prompt_version,
                    created_at,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            self._event(
                connection,
                new_id,
                "generated",
                {},
                {"status": "pending", "generation_number": old["generation_number"] + 1},
                created_at,
            )
            new_row = connection.execute(
                "SELECT * FROM resume_suggestions WHERE id = ?", (new_id,)
            ).fetchone()
        if new_row is None:
            raise RuntimeError("Suggestion regeneration failed")
        return dict(new_row)

    def undo_suggestion(
        self, suggestion_id: int, user_id: int, created_at: str
    ) -> tuple[dict[str, Any], str]:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            suggestion = connection.execute(
                """
                SELECT s.* FROM resume_suggestions s
                JOIN job_applications a ON a.id = s.application_id
                WHERE s.id = ? AND a.user_id = ?
                """,
                (suggestion_id, user_id),
            ).fetchone()
            if suggestion is None:
                raise ResumeConflictError("Suggestion not found")
            event = connection.execute(
                """
                SELECT * FROM resume_suggestion_events
                WHERE suggestion_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (suggestion_id,),
            ).fetchone()
            if event is None or event["event_type"] not in {"accepted", "rejected", "edited"}:
                raise SuggestionStateError("No recent decision can be undone")
            previous = json.loads(event["previous_value"])
            connection.execute(
                """
                UPDATE resume_suggestions
                SET status = ?, suggested_text = ?, clarification_required = ?, decided_at = NULL
                WHERE id = ?
                """,
                (
                    previous["status"],
                    previous["suggested_text"],
                    int(previous["clarification_required"]),
                    suggestion_id,
                ),
            )
            self._event(
                connection,
                suggestion_id,
                "undone",
                {
                    "status": suggestion["status"],
                    "suggested_text": suggestion["suggested_text"],
                },
                previous,
                created_at,
            )
            updated = connection.execute(
                "SELECT * FROM resume_suggestions WHERE id = ?", (suggestion_id,)
            ).fetchone()
        if updated is None:
            raise RuntimeError("Suggestion undo failed")
        return dict(updated), event["event_type"]

    def create_optimized_version(
        self,
        user_id: int,
        application_id: int,
        expected_version_id: int,
        created_at: str,
    ) -> dict[str, Any]:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            resume = connection.execute(
                """
                SELECT r.*, v.content FROM resumes r
                JOIN resume_versions v ON v.id = r.current_version_id
                WHERE r.user_id = ? AND r.source_application_id = ?
                  AND r.deleted_at IS NULL
                """,
                (user_id, application_id),
            ).fetchone()
            if resume is None:
                raise ResumeConflictError("Resume not found")
            if resume["current_version_id"] != expected_version_id:
                raise ResumeConflictError("Current resume version changed")
            suggestions = connection.execute(
                """
                SELECT * FROM resume_suggestions
                WHERE application_id = ? AND resume_version_id = ?
                  AND status IN ('accepted', 'edited')
                ORDER BY id ASC
                """,
                (application_id, expected_version_id),
            ).fetchall()
            if not suggestions:
                raise VersionCreationError("No accepted suggestions")
            content = resume["content"]
            for suggestion in suggestions:
                source = suggestion["source_text"]
                if content.count(source) != 1:
                    raise VersionCreationError(
                        "Suggestion source is missing or ambiguous in current version"
                    )
                content = content.replace(source, suggestion["suggested_text"], 1)
            if content == resume["content"]:
                raise VersionCreationError("Suggestions did not change resume content")
            next_number = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 FROM resume_versions WHERE resume_id = ?",
                (resume["id"],),
            ).fetchone()[0]
            cursor = connection.execute(
                """
                INSERT INTO resume_versions
                    (resume_id, parent_version_id, version_number, source_type,
                     content, content_hash, created_at)
                VALUES (?, ?, ?, 'optimized', ?, ?, ?)
                """,
                (
                    resume["id"],
                    expected_version_id,
                    next_number,
                    content,
                    self._hash(content),
                    created_at,
                ),
            )
            new_version_id = int(cursor.lastrowid or 0)
            self._after_version_insert(connection, new_version_id)
            connection.execute(
                "UPDATE resumes SET current_version_id = ?, updated_at = ? WHERE id = ?",
                (new_version_id, created_at, resume["id"]),
            )
            version = connection.execute(
                "SELECT * FROM resume_versions WHERE id = ?", (new_version_id,)
            ).fetchone()
        if version is None:
            raise RuntimeError("Version creation failed")
        return dict(version)

    def restore_version(
        self, version_id: int, user_id: int, created_at: str
    ) -> dict[str, Any]:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            target = connection.execute(
                """
                SELECT v.*, r.current_version_id FROM resume_versions v
                JOIN resumes r ON r.id = v.resume_id
                WHERE v.id = ? AND r.user_id = ? AND r.deleted_at IS NULL
                """,
                (version_id, user_id),
            ).fetchone()
            if target is None:
                raise ResumeConflictError("Version not found")
            next_number = connection.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 FROM resume_versions WHERE resume_id = ?",
                (target["resume_id"],),
            ).fetchone()[0]
            cursor = connection.execute(
                """
                INSERT INTO resume_versions
                    (resume_id, parent_version_id, version_number, source_type,
                     content, content_hash, created_at)
                VALUES (?, ?, ?, 'restored', ?, ?, ?)
                """,
                (
                    target["resume_id"],
                    target["current_version_id"],
                    next_number,
                    target["content"],
                    target["content_hash"],
                    created_at,
                ),
            )
            new_id = int(cursor.lastrowid or 0)
            self._after_version_insert(connection, new_id)
            connection.execute(
                "UPDATE resumes SET current_version_id = ?, updated_at = ? WHERE id = ?",
                (new_id, created_at, target["resume_id"]),
            )
            version = connection.execute(
                "SELECT * FROM resume_versions WHERE id = ?", (new_id,)
            ).fetchone()
        if version is None:
            raise RuntimeError("Version restore failed")
        return dict(version)

    def _after_version_insert(
        self, connection: Any, version_id: int
    ) -> None:
        return None

    @staticmethod
    def _event(
        connection: Any,
        suggestion_id: int,
        event_type: str,
        previous_value: dict[str, Any],
        new_value: dict[str, Any],
        created_at: str,
    ) -> None:
        connection.execute(
            """
            INSERT INTO resume_suggestion_events
                (suggestion_id, event_type, previous_value, new_value, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                suggestion_id,
                event_type,
                json.dumps(previous_value, ensure_ascii=False),
                json.dumps(new_value, ensure_ascii=False),
                created_at,
            ),
        )

    @staticmethod
    def _hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()
