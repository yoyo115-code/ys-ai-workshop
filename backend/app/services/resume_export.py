import hashlib
import re
import secrets
import tempfile
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.models.domain import PublicUser
from app.repositories.resume_export import (
    ResumeExportConflictError,
    ResumeExportRepository,
)
from app.schemas.resume_export import CreateResumeExportRequest, StructuredResume
from app.services.auth import utc_now
from app.services.document_rendering import DocumentRenderError, ResumeDocumentRenderer
from app.services.resume_structure import ResumeStructureService
from app.services.storage import StorageError, StorageProvider
from app.services.usage import DailyUsageService, RESUME_EXPORT


class ResumeExportService:
    def __init__(
        self,
        repository: ResumeExportRepository,
        structure_service: ResumeStructureService,
        renderer: ResumeDocumentRenderer,
        storage: StorageProvider,
        retention_days: int = 7,
        daily_usage_service: DailyUsageService | None = None,
    ) -> None:
        self.repository = repository
        self.structure_service = structure_service
        self.renderer = renderer
        self.storage = storage
        self.retention_days = retention_days
        self.daily_usage_service = daily_usage_service

    def preview(self, user: PublicUser, version_id: int) -> dict[str, Any]:
        context = self._version(user, version_id)
        try:
            parsed = self.structure_service.parse(context["content"])
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "structure_unavailable", "message": str(exc)},
            ) from exc
        return {
            "version_id": context["id"],
            "resume_id": context["resume_id"],
            "version_number": context["version_number"],
            "company_name": context["company_name"],
            "job_title": context["job_title"],
            "source_content_hash": context["content_hash"],
            "parse_status": parsed.status,
            "parse_warnings": parsed.warnings,
            "resume": parsed.resume.model_dump(),
        }

    def create_export(
        self,
        user: PublicUser,
        version_id: int,
        data: CreateResumeExportRequest,
    ) -> dict[str, Any]:
        context = self._version(user, version_id)
        if data.resume is None:
            try:
                resume = self.structure_service.parse(context["content"]).resume
            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail={"code": "structure_unavailable", "message": str(exc)},
                ) from exc
        else:
            resume = data.resume
        if resume.original_text != context["content"]:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "source_version_changed",
                    "message": "结构化预览与当前 ResumeVersion 原文不一致，请重新打开预览",
                },
            )
        if not self._has_renderable_content(resume):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "empty_resume_structure",
                    "message": "结构化简历没有可导出的内容",
                },
            )

        structured_content = resume.model_dump_json()
        structure_hash = self._hash_bytes(structured_content.encode("utf-8"))
        filename = self.safe_filename(
            resume.basics.name or user["display_name"],
            context["company_name"],
            context["job_title"],
            context["version_number"],
            data.format,
        )
        now_dt = datetime.now(timezone.utc)
        now = now_dt.isoformat()
        expires_at = (now_dt + timedelta(days=self.retention_days)).isoformat()
        if self.daily_usage_service is not None:
            self.daily_usage_service.consume(user, RESUME_EXPORT)
        try:
            record = self.repository.create_export(
                user["id"],
                context,
                data.template_key,
                data.format,
                data.paper_size,
                data.language,
                filename,
                structured_content,
                structure_hash,
                now,
                expires_at,
            )
        except ResumeExportConflictError as exc:
            raise HTTPException(status_code=404, detail="简历版本不存在") from exc

        export_id = record["id"]
        object_key = (
            f"users/{user['id']}/resume-exports/"
            f"{secrets.token_urlsafe(24)}.{data.format}"
        )
        temporary_path: Path | None = None
        try:
            self.repository.mark_generating(export_id, user["id"], utc_now())
            with tempfile.NamedTemporaryFile(
                prefix=f"ys-resume-export-{export_id}-",
                suffix=f".{data.format}",
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
            self.renderer.render(
                resume,
                data.template_key,
                data.format,
                data.paper_size,
                data.language,
                temporary_path,
            )
            content = temporary_path.read_bytes()
            if not content:
                raise DocumentRenderError(
                    "empty_export_file", "Document renderer produced an empty file"
                )
            self.storage.put(user["id"], object_key, content)
            self.repository.complete_export(
                export_id,
                user["id"],
                object_key,
                self._hash_bytes(content),
                utc_now(),
            )
        except DocumentRenderError as exc:
            self._delete_partial(user["id"], object_key)
            self.repository.fail_export(export_id, user["id"], exc.code, utc_now())
            status = 503 if exc.code.endswith("unavailable") else 422
            raise HTTPException(
                status_code=status,
                detail={"code": exc.code, "message": exc.message},
            ) from exc
        except Exception as exc:
            self._delete_partial(user["id"], object_key)
            try:
                self.repository.fail_export(
                    export_id, user["id"], "export_generation_failed", utc_now()
                )
            except ResumeExportConflictError:
                pass
            raise HTTPException(
                status_code=500,
                detail={
                    "code": "export_generation_failed",
                    "message": "简历导出失败，未保留不完整文件",
                },
            ) from exc
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        completed = self.repository.get_export(export_id, user["id"])
        if completed is None:
            raise HTTPException(status_code=500, detail="导出记录读取失败")
        return self._response(completed)

    def list_exports(
        self, user: PublicUser, version_id: int | None = None
    ) -> list[dict[str, Any]]:
        if version_id is not None:
            self._version(user, version_id)
        return [
            self._response(row)
            for row in self.repository.list_exports(user["id"], version_id)
        ]

    def get_export(self, user: PublicUser, export_id: int) -> dict[str, Any]:
        row = self.repository.get_export(export_id, user["id"])
        if row is None:
            raise HTTPException(status_code=404, detail="导出记录不存在")
        return self._response(row)

    def download(
        self, user: PublicUser, export_id: int
    ) -> tuple[bytes | None, str | None, dict[str, Any]]:
        row = self.repository.get_export(export_id, user["id"])
        if row is None:
            raise HTTPException(status_code=404, detail="导出记录不存在")
        if self._is_expired(row):
            raise HTTPException(
                status_code=410,
                detail={"code": "export_expired", "message": "导出文件已到期，请重新生成"},
            )
        if row["status"] != "ready" or not row["object_key"]:
            raise HTTPException(status_code=409, detail="导出文件尚未就绪")
        try:
            url = self.storage.generate_download_url(user["id"], row["object_key"])
            content = None if url else self.storage.get(user["id"], row["object_key"])
        except StorageError as exc:
            raise HTTPException(
                status_code=410,
                detail={"code": "export_file_missing", "message": "导出文件已不存在"},
            ) from exc
        return content, url, row

    def delete_export(self, user: PublicUser, export_id: int) -> None:
        row = self.repository.get_export(export_id, user["id"])
        if row is None:
            raise HTTPException(status_code=404, detail="导出记录不存在")
        if row["object_key"]:
            try:
                self.storage.delete(user["id"], row["object_key"])
            except Exception as exc:
                raise HTTPException(
                    status_code=500,
                    detail={"code": "export_delete_failed", "message": "导出文件删除失败"},
                ) from exc
        if not self.repository.mark_deleted(export_id, user["id"], utc_now()):
            raise HTTPException(status_code=409, detail="导出记录状态已变化")

    def cleanup_expired(self, now: str | None = None, limit: int = 200) -> dict[str, int]:
        cutoff = now or utc_now()
        deleted = 0
        failed = 0
        for row in self.repository.list_expired(cutoff, limit):
            try:
                if row["object_key"]:
                    self.storage.delete(row["user_id"], row["object_key"])
                if self.repository.mark_deleted(row["id"], row["user_id"], cutoff):
                    deleted += 1
            except Exception:
                failed += 1
        return {"deleted": deleted, "failed": failed}

    def _version(self, user: PublicUser, version_id: int) -> dict[str, Any]:
        context = self.repository.get_version_context(version_id, user["id"])
        if context is None:
            raise HTTPException(status_code=404, detail="简历版本不存在")
        return context

    def _delete_partial(self, user_id: int, object_key: str) -> None:
        try:
            self.storage.delete(user_id, object_key)
        except Exception:
            pass

    @staticmethod
    def safe_filename(
        name: str,
        company_name: str,
        job_title: str,
        version_number: int,
        extension: str,
    ) -> str:
        parts = [
            ResumeExportService._filename_component(name, "Resume"),
            ResumeExportService._filename_component(company_name, ""),
            ResumeExportService._filename_component(job_title, ""),
            f"v{version_number}",
        ]
        base = "_".join(part for part in parts if part)
        base = base[:140].rstrip("._- ") or "Resume"
        return f"{base}.{extension}"

    @staticmethod
    def _filename_component(value: str, fallback: str) -> str:
        normalized = unicodedata.normalize("NFKC", value or "")
        normalized = normalized.replace("..", " ")
        normalized = re.sub(r"[\\/:*?\"<>|\x00-\x1f\x7f]+", " ", normalized)
        normalized = re.sub(
            r"[^\w\u3400-\u9fff-]+", "_", normalized, flags=re.UNICODE
        )
        normalized = re.sub(r"_+", "_", normalized).strip("._- ")
        return normalized[:40].rstrip("._- ") or fallback

    @staticmethod
    def _has_renderable_content(resume: StructuredResume) -> bool:
        return bool(
            resume.basics.name
            or resume.basics.summary
            or resume.education
            or resume.experience
            or resume.projects
            or resume.skills
            or resume.certifications
            or resume.awards
            or resume.additional_information
        )

    @staticmethod
    def _hash_bytes(value: bytes) -> str:
        return hashlib.sha256(value).hexdigest()

    @staticmethod
    def _is_expired(row: dict[str, Any]) -> bool:
        expires_at = row.get("expires_at")
        if not expires_at:
            return False
        try:
            return datetime.fromisoformat(expires_at) <= datetime.now(timezone.utc)
        except ValueError:
            return True

    @classmethod
    def _response(cls, row: dict[str, Any]) -> dict[str, Any]:
        expired = cls._is_expired(row)
        status = "expired" if expired and row["status"] == "ready" else row["status"]
        return {
            "id": row["id"],
            "resume_id": row["resume_id"],
            "resume_version_id": row["resume_version_id"],
            "version_number": row["version_number"],
            "company_name": row["company_name"],
            "job_title": row["job_title"],
            "template_key": row["template_key"],
            "format": row["format"],
            "paper_size": row["paper_size"],
            "language": row["language"],
            "status": status,
            "filename": row["filename"],
            "source_content_hash": row["source_content_hash"],
            "content_hash": row["content_hash"],
            "error_code": row["error_code"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "expires_at": row["expires_at"],
            "download_url": (
                f"/career/resume-exports/{row['id']}/download"
                if status == "ready"
                else None
            ),
        }
