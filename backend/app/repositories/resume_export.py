from typing import Any

from app.repositories.database import Database


class ResumeExportConflictError(Exception):
    pass


class ResumeExportRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def get_version_context(self, version_id: int, user_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT v.*, r.name AS resume_name, r.user_id,
                       a.company_name, a.job_title, a.language AS application_language
                FROM resume_versions v
                JOIN resumes r ON r.id = v.resume_id
                JOIN job_applications a ON a.id = r.source_application_id
                WHERE v.id = ? AND r.user_id = ? AND r.deleted_at IS NULL
                """,
                (version_id, user_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def create_export(
        self,
        user_id: int,
        context: dict[str, Any],
        template_key: str,
        export_format: str,
        paper_size: str,
        language: str,
        filename: str,
        structured_content: str,
        structure_hash: str,
        created_at: str,
        expires_at: str,
    ) -> dict[str, Any]:
        with self.database.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            owned = connection.execute(
                """
                SELECT 1 FROM resume_versions v
                JOIN resumes r ON r.id = v.resume_id
                WHERE v.id = ? AND r.user_id = ? AND r.deleted_at IS NULL
                """,
                (context["id"], user_id),
            ).fetchone()
            if owned is None:
                raise ResumeExportConflictError("ResumeVersion not found")
            cursor = connection.execute(
                """
                INSERT INTO resume_exports
                    (user_id, resume_id, resume_version_id, template_key, format,
                     paper_size, language, status, filename, source_content_hash,
                     structured_content, structure_hash, created_at, updated_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    context["resume_id"],
                    context["id"],
                    template_key,
                    export_format,
                    paper_size,
                    language,
                    filename,
                    context["content_hash"],
                    structured_content,
                    structure_hash,
                    created_at,
                    created_at,
                    expires_at,
                ),
            )
            export_id = int(cursor.lastrowid or 0)
            self._after_export_insert(export_id)
            row = connection.execute(
                "SELECT * FROM resume_exports WHERE id = ?", (export_id,)
            ).fetchone()
        if row is None:
            raise RuntimeError("Resume export record creation failed")
        return dict(row)

    def mark_generating(self, export_id: int, user_id: int, updated_at: str) -> None:
        self._transition(export_id, user_id, "pending", "generating", updated_at)

    def complete_export(
        self,
        export_id: int,
        user_id: int,
        object_key: str,
        content_hash: str,
        updated_at: str,
    ) -> dict[str, Any]:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE resume_exports
                SET status = 'ready', object_key = ?, content_hash = ?,
                    error_code = NULL, updated_at = ?
                WHERE id = ? AND user_id = ? AND status = 'generating'
                  AND deleted_at IS NULL
                """,
                (object_key, content_hash, updated_at, export_id, user_id),
            )
            if cursor.rowcount != 1:
                raise ResumeExportConflictError("Illegal export status transition")
            row = connection.execute(
                "SELECT * FROM resume_exports WHERE id = ?", (export_id,)
            ).fetchone()
        if row is None:
            raise RuntimeError("Resume export completion failed")
        return dict(row)

    def fail_export(
        self, export_id: int, user_id: int, error_code: str, updated_at: str
    ) -> dict[str, Any]:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE resume_exports
                SET status = 'failed', object_key = NULL, content_hash = NULL,
                    error_code = ?, updated_at = ?
                WHERE id = ? AND user_id = ? AND status IN ('pending', 'generating')
                  AND deleted_at IS NULL
                """,
                (error_code, updated_at, export_id, user_id),
            )
            if cursor.rowcount != 1:
                raise ResumeExportConflictError("Illegal export status transition")
            row = connection.execute(
                "SELECT * FROM resume_exports WHERE id = ?", (export_id,)
            ).fetchone()
        if row is None:
            raise RuntimeError("Resume export failure update failed")
        return dict(row)

    def get_export(self, export_id: int, user_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT e.*, v.version_number, a.company_name, a.job_title
                FROM resume_exports e
                JOIN resume_versions v ON v.id = e.resume_version_id
                JOIN resumes r ON r.id = e.resume_id
                JOIN job_applications a ON a.id = r.source_application_id
                WHERE e.id = ? AND e.user_id = ? AND e.deleted_at IS NULL
                """,
                (export_id, user_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_exports(
        self, user_id: int, version_id: int | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        parameters: list[Any] = [user_id]
        version_clause = ""
        if version_id is not None:
            version_clause = "AND e.resume_version_id = ?"
            parameters.append(version_id)
        parameters.append(limit)
        with self.database.connect() as connection:
            rows = connection.execute(
                f"""
                SELECT e.*, v.version_number, a.company_name, a.job_title
                FROM resume_exports e
                JOIN resume_versions v ON v.id = e.resume_version_id
                JOIN resumes r ON r.id = e.resume_id
                JOIN job_applications a ON a.id = r.source_application_id
                WHERE e.user_id = ? AND e.deleted_at IS NULL
                {version_clause}
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [dict(row) for row in rows]

    def mark_deleted(self, export_id: int, user_id: int, deleted_at: str) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE resume_exports
                SET status = 'deleted', deleted_at = ?, updated_at = ?
                WHERE id = ? AND user_id = ? AND deleted_at IS NULL
                """,
                (deleted_at, deleted_at, export_id, user_id),
            )
        return cursor.rowcount == 1

    def list_expired(self, now: str, limit: int = 200) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM resume_exports
                WHERE deleted_at IS NULL AND expires_at IS NOT NULL
                  AND expires_at <= ?
                ORDER BY expires_at ASC, id ASC
                LIMIT ?
                """,
                (now, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_object_keys_for_user(self, user_id: int) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, object_key FROM resume_exports
                WHERE user_id = ? AND object_key IS NOT NULL AND deleted_at IS NULL
                ORDER BY id
                """,
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_object_keys_for_application(
        self, user_id: int, application_id: int
    ) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT e.id, e.user_id, e.object_key FROM resume_exports e
                JOIN resumes r ON r.id = e.resume_id
                WHERE e.user_id = ? AND r.source_application_id = ?
                  AND e.object_key IS NOT NULL AND e.deleted_at IS NULL
                ORDER BY e.id
                """,
                (user_id, application_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_object_keys_for_resume(
        self, user_id: int, resume_id: int
    ) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, object_key FROM resume_exports
                WHERE user_id = ? AND resume_id = ?
                  AND object_key IS NOT NULL AND deleted_at IS NULL
                ORDER BY id
                """,
                (user_id, resume_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def _transition(
        self,
        export_id: int,
        user_id: int,
        current_status: str,
        target_status: str,
        updated_at: str,
    ) -> None:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE resume_exports SET status = ?, updated_at = ?
                WHERE id = ? AND user_id = ? AND status = ? AND deleted_at IS NULL
                """,
                (target_status, updated_at, export_id, user_id, current_status),
            )
        if cursor.rowcount != 1:
            raise ResumeExportConflictError("Illegal export status transition")

    @staticmethod
    def _after_export_insert(export_id: int) -> None:
        return None
