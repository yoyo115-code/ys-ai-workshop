import json
import sqlite3
from typing import Any

from app.repositories.database import Database


class CareerRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def create_application(
        self,
        user_id: int,
        company_name: str,
        job_title: str,
        location: str,
        job_description: str,
        language: str,
        status: str,
        source_type: str,
        original_filename: str | None,
        extracted_text: str,
        content_hash: str,
        parse_status: str,
        parse_error: str | None,
        created_at: str,
    ) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO job_applications
                    (user_id, company_name, job_title, location, job_description,
                     language, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    company_name,
                    job_title,
                    location,
                    job_description,
                    language,
                    status,
                    created_at,
                    created_at,
                ),
            )
            application_id = int(cursor.lastrowid or 0)
            connection.execute(
                """
                INSERT INTO resume_sources
                    (application_id, source_type, original_filename, extracted_text,
                     content_hash, parse_status, parse_error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    application_id,
                    source_type,
                    original_filename,
                    extracted_text,
                    content_hash,
                    parse_status,
                    parse_error,
                    created_at,
                ),
            )
        return application_id

    def list_applications(self, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, company_name, job_title, location, language, status,
                       created_at, updated_at
                FROM job_applications
                WHERE user_id = ?
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_application(self, application_id: int, user_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT a.*, r.source_type, r.original_filename, r.extracted_text,
                       r.parse_status, r.parse_error
                FROM job_applications a
                JOIN resume_sources r ON r.application_id = a.id
                WHERE a.id = ? AND a.user_id = ?
                """,
                (application_id, user_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def delete_application(self, application_id: int, user_id: int) -> bool:
        with self.database.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM job_applications WHERE id = ? AND user_id = ?",
                (application_id, user_id),
            )
        return cursor.rowcount > 0

    def latest_analysis(self, application_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM match_analyses
                WHERE application_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (application_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def latest_completed_analysis(self, application_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM match_analyses
                WHERE application_id = ? AND status = 'completed'
                ORDER BY id DESC
                LIMIT 1
                """,
                (application_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def create_analysis(
        self,
        application_id: int,
        provider: str,
        model: str,
        prompt_version: str,
        created_at: str,
    ) -> int:
        with self.database.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO match_analyses
                    (application_id, provider, model, prompt_version, status, created_at)
                VALUES (?, ?, ?, ?, 'analyzing', ?)
                """,
                (application_id, provider, model, prompt_version, created_at),
            )
            analysis_id = int(cursor.lastrowid or 0)
            connection.execute(
                """
                UPDATE job_applications SET status = 'analyzing', updated_at = ?
                WHERE id = ?
                """,
                (created_at, application_id),
            )
        return analysis_id

    def complete_analysis(
        self,
        analysis_id: int,
        application_id: int,
        payload: dict[str, Any],
        updated_at: str,
    ) -> None:
        categories = (
            "covered_requirements",
            "partially_covered_requirements",
            "missing_requirements",
            "uncertain_requirements",
            "resume_expression_issues",
            "qualification_risks",
        )
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE match_analyses
                SET overall_alignment = ?, summary = ?, limitations = ?,
                    status = 'completed', error_code = NULL
                WHERE id = ?
                """,
                (
                    payload["overall_alignment"],
                    payload["summary"],
                    json.dumps(payload["analysis_limitations"], ensure_ascii=False),
                    analysis_id,
                ),
            )
            for category in categories:
                for index, item in enumerate(payload[category]):
                    connection.execute(
                        """
                        INSERT INTO match_items
                            (analysis_id, category, jd_requirement, resume_evidence,
                             explanation, confidence_level, sort_order)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            analysis_id,
                            category,
                            item["jd_requirement"],
                            item["resume_evidence"],
                            item["explanation"],
                            item["confidence_level"],
                            index,
                        ),
                    )
            connection.execute(
                """
                UPDATE job_applications SET status = 'completed', updated_at = ?
                WHERE id = ?
                """,
                (updated_at, application_id),
            )

    def fail_analysis(
        self,
        analysis_id: int,
        application_id: int,
        error_code: str,
        updated_at: str,
    ) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE match_analyses SET status = 'failed', error_code = ?
                WHERE id = ?
                """,
                (error_code, analysis_id),
            )
            connection.execute(
                """
                UPDATE job_applications SET status = 'analysis_failed', updated_at = ?
                WHERE id = ?
                """,
                (updated_at, application_id),
            )

    def analysis_with_items(self, analysis_id: int) -> dict[str, Any] | None:
        with self.database.connect() as connection:
            analysis = connection.execute(
                "SELECT * FROM match_analyses WHERE id = ?", (analysis_id,)
            ).fetchone()
            if analysis is None:
                return None
            items = connection.execute(
                """
                SELECT category, jd_requirement, resume_evidence, explanation,
                       confidence_level
                FROM match_items
                WHERE analysis_id = ?
                ORDER BY category, sort_order, id
                """,
                (analysis_id,),
            ).fetchall()
        result = dict(analysis)
        result["items"] = [dict(item) for item in items]
        return result
