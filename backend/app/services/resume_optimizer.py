import difflib
import json
import re
import time
from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from app.models.domain import PublicUser
from app.core.config import Settings
from app.prompts.resume_suggestion_v1 import (
    PROMPT_VERSION,
    build_resume_suggestion_prompt,
)
from app.repositories.career import CareerRepository
from app.repositories.resume import (
    ResumeConflictError,
    ResumeRepository,
    SuggestionStateError,
    VersionCreationError,
)
from app.repositories.workshop import WorkshopRepository
from app.schemas.resume_optimizer import ResumeSuggestionPayload, UpdateSuggestionRequest
from app.services.auth import utc_now
from app.services.llm import LLMProvider
from app.services.usage import (
    DailyUsageService,
    SUGGESTION_GENERATION,
    SUGGESTION_REGENERATION,
)


SUGGESTION_PROVIDER = "deepseek"
SUGGESTION_MODEL = "deepseek-chat"
TECH_TERMS = {
    "python",
    "java",
    "javascript",
    "typescript",
    "react",
    "vue",
    "angular",
    "fastapi",
    "django",
    "flask",
    "spring",
    "sql",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "docker",
    "kubernetes",
    "aws",
    "azure",
    "gcp",
    "pytorch",
    "tensorflow",
    "spark",
    "hadoop",
    "机器学习",
    "深度学习",
}
PROPER_NOUN_WHITELIST = {
    "built",
    "led",
    "developed",
    "improved",
    "created",
    "managed",
    "designed",
    "implemented",
    "collaborated",
    "reduced",
    "increased",
    "delivered",
    "optimized",
    "responsible",
    "worked",
    "used",
    "using",
    "the",
    "this",
    "and",
    "for",
    "with",
}


class ResumeOptimizerService:
    def __init__(
        self,
        repository: ResumeRepository,
        career_repository: CareerRepository,
        workshop_repository: WorkshopRepository,
        llm_provider: LLMProvider,
        daily_usage_service: DailyUsageService,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.career_repository = career_repository
        self.workshop_repository = workshop_repository
        self.llm_provider = llm_provider
        self.daily_usage_service = daily_usage_service
        self.settings = settings

    def get_workspace(
        self, user: PublicUser, application_id: int
    ) -> dict[str, Any]:
        application = self._application(user, application_id)
        resume, version = self._ensure_resume(user, application)
        suggestions = self.repository.list_suggestions(
            application_id, version["id"], user["id"]
        )
        return self._workspace_response(application, resume, version, suggestions)

    def generate_suggestions(
        self, user: PublicUser, application_id: int, retry: bool = False
    ) -> dict[str, Any]:
        application = self._application(user, application_id)
        resume, version = self._ensure_resume(user, application)
        active = self.repository.active_suggestions(
            application_id, version["id"], user["id"]
        )
        if active and not retry:
            all_suggestions = self.repository.list_suggestions(
                application_id, version["id"], user["id"]
            )
            return self._workspace_response(
                application, resume, version, all_suggestions
            )

        self._validate_input_lengths(
            version["content"], application["job_description"]
        )

        match_context = self._match_context(application_id)
        prompt = build_resume_suggestion_prompt(
            version["content"],
            application["job_description"],
            match_context,
            application["language"],
        )
        started = time.perf_counter()
        try:
            self.daily_usage_service.consume(user, SUGGESTION_GENERATION)
            raw_output = self.llm_provider.generate(prompt, SUGGESTION_PROVIDER)
            payload = self._validate_output(
                raw_output, version["content"], application["job_description"]
            )
        except HTTPException:
            self._record_activity(
                user, application_id, "error", started, "provider_error"
            )
            raise
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            self._record_activity(
                user, application_id, "error", started, "invalid_suggestion_output"
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "invalid_suggestion_output",
                    "message": "模型建议不符合结构、证据或事实约束，请重试",
                },
            ) from exc
        except Exception as exc:
            self._record_activity(
                user, application_id, "error", started, "provider_failure"
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "provider_failure",
                    "message": "建议生成失败，请稍后重试",
                },
            ) from exc

        created = self.repository.create_suggestions(
            application_id,
            version["id"],
            user["id"],
            [item.model_dump() for item in payload.suggestions],
            PROMPT_VERSION,
            utc_now(),
            replace_active=retry,
        )
        self._record_activity(
            user,
            application_id,
            "success",
            started,
            metadata={"suggestion_count": len(created), "version_id": version["id"]},
        )
        all_suggestions = self.repository.list_suggestions(
            application_id, version["id"], user["id"]
        )
        return self._workspace_response(
            application, resume, version, all_suggestions
        )

    def update_suggestion(
        self,
        user: PublicUser,
        suggestion_id: int,
        data: UpdateSuggestionRequest,
    ) -> dict[str, Any]:
        suggestion = self._suggestion(user, suggestion_id)
        target_status = {
            "accept": "accepted",
            "reject": "rejected",
            "edit": "edited",
        }[data.action]
        if data.action == "accept" and (
            suggestion["risk_level"] == "high"
            or bool(suggestion["clarification_required"])
        ):
            raise HTTPException(
                status_code=409,
                detail="高风险或需要补充事实的建议必须先手工编辑并确认",
            )
        if data.action == "edit":
            if not data.suggested_text or not data.suggested_text.strip():
                raise HTTPException(status_code=422, detail="编辑后的建议不能为空")
            if (
                suggestion["risk_level"] == "high"
                or bool(suggestion["clarification_required"])
            ) and not data.confirm_risk:
                raise HTTPException(
                    status_code=409, detail="请确认已核实高风险或缺失事实"
                )
        try:
            updated = self.repository.update_suggestion(
                suggestion_id,
                user["id"],
                target_status,
                utc_now(),
                data.suggested_text,
            )
        except ResumeConflictError as exc:
            raise HTTPException(status_code=404, detail="建议不存在") from exc
        except SuggestionStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return self._suggestion_response(updated)

    def regenerate_suggestion(
        self, user: PublicUser, suggestion_id: int
    ) -> dict[str, Any]:
        suggestion = self._suggestion(user, suggestion_id)
        version = self.repository.get_version(
            suggestion["resume_version_id"], user["id"]
        )
        if version is None:
            raise HTTPException(status_code=404, detail="简历版本不存在")
        application = self._application(user, suggestion["application_id"])
        self._validate_input_lengths(
            version["content"], application["job_description"]
        )
        prompt = build_resume_suggestion_prompt(
            version["content"],
            application["job_description"],
            self._match_context(application["id"]),
            application["language"],
            focus_source_text=suggestion["source_text"],
        )
        started = time.perf_counter()
        try:
            self.daily_usage_service.consume(user, SUGGESTION_REGENERATION)
            raw_output = self.llm_provider.generate(prompt, SUGGESTION_PROVIDER)
            payload = self._validate_output(
                raw_output,
                version["content"],
                application["job_description"],
                focus_source_text=suggestion["source_text"],
            )
            if len(payload.suggestions) != 1:
                raise ValueError("Regeneration must return exactly one suggestion")
        except HTTPException:
            self._record_activity(
                user, application["id"], "error", started, "provider_error"
            )
            raise
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            self._record_activity(
                user,
                application["id"],
                "error",
                started,
                "invalid_suggestion_output",
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "invalid_suggestion_output",
                    "message": "重新生成的建议不符合证据约束",
                },
            ) from exc
        except Exception as exc:
            self._record_activity(
                user, application["id"], "error", started, "provider_failure"
            )
            raise HTTPException(
                status_code=502,
                detail={"code": "provider_failure", "message": "建议重新生成失败"},
            ) from exc
        try:
            created = self.repository.replace_suggestion(
                suggestion_id,
                user["id"],
                payload.suggestions[0].model_dump(),
                PROMPT_VERSION,
                utc_now(),
            )
        except ResumeConflictError as exc:
            raise HTTPException(status_code=404, detail="建议不存在") from exc
        except SuggestionStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        self._record_activity(
            user,
            application["id"],
            "success",
            started,
            metadata={"suggestion_id": created["id"], "regenerated_from": suggestion_id},
        )
        return self._suggestion_response(created)

    def _validate_input_lengths(self, resume_text: str, job_description: str) -> None:
        for value, limit, input_type, label in (
            (resume_text, self.settings.max_resume_characters, "resume", "简历"),
            (
                job_description,
                self.settings.max_job_description_characters,
                "job_description",
                "岗位 JD",
            ),
        ):
            if len(value) > limit:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "input_too_long",
                        "input_type": input_type,
                        "limit": limit,
                        "message": f"{label}超过 {limit} 字符限制",
                    },
                )

    def undo_suggestion(
        self, user: PublicUser, suggestion_id: int
    ) -> dict[str, Any]:
        try:
            suggestion, event_type = self.repository.undo_suggestion(
                suggestion_id, user["id"], utc_now()
            )
        except ResumeConflictError as exc:
            raise HTTPException(status_code=404, detail="建议不存在") from exc
        except SuggestionStateError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {
            "suggestion": self._suggestion_response(suggestion),
            "undone_event_type": event_type,
        }

    def create_version(
        self, user: PublicUser, application_id: int
    ) -> dict[str, Any]:
        application = self._application(user, application_id)
        _, current_version = self._ensure_resume(user, application)
        try:
            return self._version_response(
                self.repository.create_optimized_version(
                    user["id"], application_id, current_version["id"], utc_now()
                )
            )
        except ResumeConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except VersionCreationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail="版本创建失败，事务已回滚，未保存任何更改",
            ) from exc

    def list_versions(self, user: PublicUser, resume_id: int) -> list[dict[str, Any]]:
        versions = self.repository.list_versions(resume_id, user["id"])
        if not versions:
            raise HTTPException(status_code=404, detail="简历不存在")
        return [self._version_response(version) for version in versions]

    def get_version(self, user: PublicUser, version_id: int) -> dict[str, Any]:
        version = self.repository.get_version(version_id, user["id"])
        if version is None:
            raise HTTPException(status_code=404, detail="简历版本不存在")
        return self._version_response(version)

    def compare_versions(
        self, user: PublicUser, version_id: int, other_version_id: int
    ) -> dict[str, Any]:
        first = self.repository.get_version(version_id, user["id"])
        second = self.repository.get_version(other_version_id, user["id"])
        if first is None or second is None:
            raise HTTPException(status_code=404, detail="简历版本不存在")
        if first["resume_id"] != second["resume_id"]:
            raise HTTPException(status_code=409, detail="只能比较同一份简历的版本")
        changes: list[dict[str, Any]] = []
        matcher = difflib.SequenceMatcher(
            None, first["content"].splitlines(), second["content"].splitlines()
        )
        for operation, i1, i2, j1, j2 in matcher.get_opcodes():
            if operation == "equal":
                continue
            change_type = {
                "insert": "added",
                "delete": "deleted",
                "replace": "modified",
            }[operation]
            changes.append(
                {
                    "change_type": change_type,
                    "before": first["content"].splitlines()[i1:i2],
                    "after": second["content"].splitlines()[j1:j2],
                }
            )
        return {
            "from_version": self._version_response(first),
            "to_version": self._version_response(second),
            "changes": changes,
        }

    def restore_version(
        self, user: PublicUser, version_id: int
    ) -> dict[str, Any]:
        try:
            version = self.repository.restore_version(version_id, user["id"], utc_now())
        except ResumeConflictError as exc:
            raise HTTPException(status_code=404, detail="简历版本不存在") from exc
        return self._version_response(version)

    def _application(
        self, user: PublicUser, application_id: int
    ) -> dict[str, Any]:
        application = self.career_repository.get_application(
            application_id, user["id"]
        )
        if application is None:
            raise HTTPException(status_code=404, detail="申请记录不存在")
        if application["parse_status"] != "parsed" or not application["extracted_text"]:
            raise HTTPException(status_code=422, detail="申请没有可用的简历文本")
        return application

    def _ensure_resume(
        self, user: PublicUser, application: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        name = application["job_title"] or application["company_name"] or "Career Resume"
        return self.repository.ensure_resume(
            user["id"],
            application["id"],
            name,
            application["extracted_text"],
            utc_now(),
        )

    def _match_context(self, application_id: int) -> dict[str, Any]:
        latest = self.career_repository.latest_completed_analysis(application_id)
        if latest is None:
            raise HTTPException(
                status_code=409, detail="请先完成 Career Match 分析"
            )
        analysis = self.career_repository.analysis_with_items(latest["id"])
        if analysis is None:
            raise HTTPException(status_code=409, detail="Career Match 结果不存在")
        return {
            "overall_alignment": analysis["overall_alignment"],
            "summary": analysis["summary"],
            "items": analysis["items"],
        }

    @classmethod
    def _validate_output(
        cls,
        raw_output: str,
        resume_content: str,
        job_description: str,
        focus_source_text: str | None = None,
    ) -> ResumeSuggestionPayload:
        clean_output = raw_output.strip()
        if clean_output.startswith("```") and clean_output.endswith("```"):
            clean_output = clean_output.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        payload = ResumeSuggestionPayload.model_validate(json.loads(clean_output))
        seen_sources: set[str] = set()
        for suggestion in payload.suggestions:
            source = suggestion.source_text
            if source not in resume_content or resume_content.count(source) != 1:
                raise ValueError("source_text is missing or ambiguous")
            if source in seen_sources:
                raise ValueError("Duplicate source_text suggestions are not allowed")
            seen_sources.add(source)
            if focus_source_text is not None and source != focus_source_text:
                raise ValueError("Regenerated suggestion changed source_text")
            if suggestion.suggested_text.strip() == source.strip():
                raise ValueError("Suggestion must change the source text")
            if suggestion.resume_evidence and suggestion.resume_evidence not in resume_content:
                raise ValueError("resume_evidence is not grounded")
            if suggestion.jd_evidence and suggestion.jd_evidence not in job_description:
                raise ValueError("jd_evidence is not grounded")
            if not suggestion.resume_evidence or not suggestion.jd_evidence:
                suggestion.clarification_required = True
            risks = cls._fact_risks(source, suggestion.suggested_text, resume_content)
            if risks:
                suggestion.risk_level = "high"
                suggestion.clarification_required = True
                suggestion.reason = (
                    f"{suggestion.reason} 事实风险：{'、'.join(risks)}；需要用户核实。"
                )[:2000]
        return payload

    @staticmethod
    def _fact_risks(
        source_text: str, suggested_text: str, resume_content: str
    ) -> list[str]:
        risks: list[str] = []
        number_pattern = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?%?")
        new_numbers = set(number_pattern.findall(suggested_text)) - set(
            number_pattern.findall(source_text)
        )
        if new_numbers:
            risks.append("新增数字")

        resume_lower = resume_content.casefold()
        suggested_lower = suggested_text.casefold()
        new_tech = sorted(
            term
            for term in TECH_TERMS
            if term in suggested_lower and term not in resume_lower
        )
        if new_tech:
            risks.append("新增技术名")

        proper_pattern = re.compile(r"\b[A-Z][A-Za-z0-9.+#-]{2,}\b")
        proper_names = {
            token
            for token in proper_pattern.findall(suggested_text)
            if token.casefold() not in PROPER_NOUN_WHITELIST
            and token.casefold() not in resume_lower
        }
        chinese_entities = {
            token
            for token in re.findall(r"[\u4e00-\u9fff]{2,}(?:公司|集团|大学|学院)", suggested_text)
            if token not in resume_content
        }
        if proper_names or chinese_entities:
            risks.append("新增专有名词或机构名")
        return risks

    def _suggestion(
        self, user: PublicUser, suggestion_id: int
    ) -> dict[str, Any]:
        suggestion = self.repository.get_suggestion(suggestion_id, user["id"])
        if suggestion is None:
            raise HTTPException(status_code=404, detail="建议不存在")
        return suggestion

    @staticmethod
    def _suggestion_response(row: dict[str, Any]) -> dict[str, Any]:
        return {
            **row,
            "clarification_required": bool(row["clarification_required"]),
        }

    @staticmethod
    def _version_response(row: dict[str, Any]) -> dict[str, Any]:
        return dict(row)

    def _workspace_response(
        self,
        application: dict[str, Any],
        resume: dict[str, Any],
        version: dict[str, Any],
        suggestions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        active = [row for row in suggestions if row["status"] != "superseded"]
        return {
            "application_id": application["id"],
            "company_name": application["company_name"],
            "job_title": application["job_title"],
            "resume": {
                "id": resume["id"],
                "name": resume["name"],
                "source_application_id": resume["source_application_id"],
                "current_version_id": resume["current_version_id"],
                "created_at": resume["created_at"],
                "updated_at": resume["updated_at"],
            },
            "current_version": self._version_response(version),
            "suggestions": [self._suggestion_response(row) for row in suggestions],
            "accepted_count": sum(
                row["status"] in {"accepted", "edited"} for row in active
            ),
            "pending_count": sum(row["status"] == "pending" for row in active),
        }

    def _record_activity(
        self,
        user: PublicUser,
        application_id: int,
        status: str,
        started: float,
        error_code: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.workshop_repository.record_activity(
            user["id"],
            "resume_suggestions",
            f"application:{application_id}",
            "",
            status,
            int((time.perf_counter() - started) * 1000),
            utc_now(),
            error=error_code,
            metadata={
                "application_id": application_id,
                "provider": SUGGESTION_PROVIDER,
                "model": SUGGESTION_MODEL,
                "prompt_version": PROMPT_VERSION,
                **(metadata or {}),
            },
        )
