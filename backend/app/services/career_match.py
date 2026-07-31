import json
import time
from typing import Any

from fastapi import HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.models.domain import PublicUser
from app.prompts.career_match_v1 import PROMPT_VERSION, build_career_match_prompt
from app.repositories.career import CareerRepository
from app.repositories.workshop import WorkshopRepository
from app.schemas.career_match import MatchAnalysisPayload
from app.services.auth import utc_now
from app.services.llm import LLMProvider
from app.services.resume_parsing import ParsedResume, ResumeParseFailure, ResumeParsingService


CAREER_PROVIDER = "deepseek"
CAREER_MODEL = "deepseek-chat"
CATEGORIES = (
    "covered_requirements",
    "partially_covered_requirements",
    "missing_requirements",
    "uncertain_requirements",
    "resume_expression_issues",
    "qualification_risks",
)


class CareerMatchService:
    def __init__(
        self,
        repository: CareerRepository,
        workshop_repository: WorkshopRepository,
        resume_parser: ResumeParsingService,
        llm_provider: LLMProvider,
    ) -> None:
        self.repository = repository
        self.workshop_repository = workshop_repository
        self.resume_parser = resume_parser
        self.llm_provider = llm_provider

    async def create_application(
        self,
        user: PublicUser,
        resume_text: str,
        resume_file: UploadFile | None,
        job_description: str,
        company_name: str,
        job_title: str,
        location: str,
        language: str,
    ) -> dict[str, Any]:
        jd = job_description.strip()
        if not jd:
            raise HTTPException(status_code=422, detail="岗位 JD 不能为空")
        if language not in {"zh", "en", "bilingual"}:
            raise HTTPException(status_code=422, detail="语言必须为 zh、en 或 bilingual")
        has_text = bool(resume_text.strip())
        if has_text and resume_file is not None and resume_file.filename:
            raise HTTPException(status_code=422, detail="简历文本和简历文件只能选择一种")
        if not has_text and (resume_file is None or not resume_file.filename):
            raise HTTPException(status_code=422, detail="请粘贴简历文本或上传简历文件")

        try:
            parsed = (
                self.resume_parser.from_text(resume_text)
                if has_text
                else await self.resume_parser.from_upload(resume_file)  # type: ignore[arg-type]
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ResumeParseFailure as exc:
            application_id = self._persist_application(
                user,
                company_name,
                job_title,
                location,
                jd,
                language,
                ParsedResume(
                    source_type=exc.source_type,
                    original_filename=exc.filename,
                    extracted_text="",
                    content_hash="",
                    parse_status="failed",
                    parse_error=exc.message,
                ),
                "parse_failed",
            )
            raise HTTPException(
                status_code=422,
                detail={
                    "code": exc.code,
                    "message": exc.message,
                    "application_id": application_id,
                },
            ) from exc

        application_id = self._persist_application(
            user,
            company_name,
            job_title,
            location,
            jd,
            language,
            parsed,
            "ready",
        )
        return self.get_application(user, application_id)

    def list_applications(self, user: PublicUser) -> list[dict[str, Any]]:
        return self.repository.list_applications(user["id"])

    def get_application(
        self, user: PublicUser, application_id: int
    ) -> dict[str, Any]:
        row = self.repository.get_application(application_id, user["id"])
        if row is None:
            raise HTTPException(status_code=404, detail="申请记录不存在")
        latest = self.repository.latest_analysis(application_id)
        latest_completed = self.repository.latest_completed_analysis(application_id)
        detail = self._application_response(row)
        if latest is not None:
            detail["latest_analysis_error_code"] = latest.get("error_code")
        if latest_completed is not None:
            detail["latest_analysis"] = self._analysis_response(
                self.repository.analysis_with_items(latest_completed["id"])
            )
        return detail

    def delete_application(self, user: PublicUser, application_id: int) -> None:
        if not self.repository.delete_application(application_id, user["id"]):
            raise HTTPException(status_code=404, detail="申请记录不存在")

    def analyze(
        self, user: PublicUser, application_id: int, retry: bool = False
    ) -> dict[str, Any]:
        application = self.repository.get_application(application_id, user["id"])
        if application is None:
            raise HTTPException(status_code=404, detail="申请记录不存在")
        if application["parse_status"] != "parsed" or not application["extracted_text"]:
            raise HTTPException(status_code=422, detail="简历没有可用于分析的文本")

        latest = self.repository.latest_analysis(application_id)
        if latest is not None and latest["status"] == "analyzing":
            raise HTTPException(status_code=409, detail="该申请正在分析，请勿重复提交")
        if latest is not None and latest["status"] == "completed" and not retry:
            return self._analysis_response(
                self.repository.analysis_with_items(latest["id"])
            )

        created_at = utc_now()
        try:
            analysis_id = self.repository.create_analysis(
                application_id,
                CAREER_PROVIDER,
                CAREER_MODEL,
                PROMPT_VERSION,
                created_at,
            )
        except IntegrityError as exc:
            raise HTTPException(
                status_code=409, detail="该申请正在分析，请勿重复提交"
            ) from exc
        prompt = build_career_match_prompt(
            application["extracted_text"],
            application["job_description"],
            application["language"],
        )
        started = time.perf_counter()
        try:
            raw_output = self.llm_provider.generate(prompt, CAREER_PROVIDER)
            payload = self._validate_output(
                raw_output,
                application["extracted_text"],
                application["job_description"],
            )
        except HTTPException as exc:
            self._record_failure(
                user, application_id, analysis_id, "provider_error", started
            )
            raise
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            self._record_failure(
                user, application_id, analysis_id, "invalid_model_output", started
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "invalid_model_output",
                    "message": "模型返回的匹配分析不符合结构或证据约束，请重试",
                },
            ) from exc
        except Exception as exc:
            self._record_failure(
                user, application_id, analysis_id, "provider_failure", started
            )
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "provider_failure",
                    "message": "模型调用失败，请稍后重试",
                },
            ) from exc

        now = utc_now()
        payload_dict = payload.model_dump()
        self.repository.complete_analysis(
            analysis_id, application_id, payload_dict, now
        )
        self._record_activity(
            user,
            application_id,
            "success",
            started,
            {"analysis_id": analysis_id, "prompt_version": PROMPT_VERSION},
        )
        return self._analysis_response(
            self.repository.analysis_with_items(analysis_id)
        )

    def _persist_application(
        self,
        user: PublicUser,
        company_name: str,
        job_title: str,
        location: str,
        job_description: str,
        language: str,
        parsed: ParsedResume,
        status: str,
    ) -> int:
        now = utc_now()
        return self.repository.create_application(
            user["id"],
            company_name.strip()[:200],
            job_title.strip()[:200],
            location.strip()[:200],
            job_description[:50000],
            language,
            status,
            parsed.source_type,
            parsed.original_filename,
            parsed.extracted_text,
            parsed.content_hash,
            parsed.parse_status,
            parsed.parse_error,
            now,
        )

    @staticmethod
    def _validate_output(
        raw_output: str, resume_text: str, job_description: str
    ) -> MatchAnalysisPayload:
        clean_output = raw_output.strip()
        if clean_output.startswith("```") and clean_output.endswith("```"):
            clean_output = clean_output.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        payload = MatchAnalysisPayload.model_validate(json.loads(clean_output))
        normalized_resume = CareerMatchService._normalize(resume_text)
        normalized_jd = CareerMatchService._normalize(job_description)
        expected_confidence = {
            "covered_requirements": "strong",
            "partially_covered_requirements": "partial",
            "missing_requirements": "missing",
            "uncertain_requirements": "uncertain",
        }
        for category in CATEGORIES:
            for item in getattr(payload, category):
                if CareerMatchService._normalize(item.jd_requirement) not in normalized_jd:
                    raise ValueError("JD requirement is not grounded in the input")
                evidence = CareerMatchService._normalize(item.resume_evidence)
                if evidence and evidence not in normalized_resume:
                    raise ValueError("Resume evidence is not grounded in the input")
                required_level = expected_confidence.get(category)
                if required_level and item.confidence_level != required_level:
                    raise ValueError("Confidence level does not match category")
                if category in {
                    "covered_requirements",
                    "partially_covered_requirements",
                    "resume_expression_issues",
                } and not evidence:
                    raise ValueError("This category requires resume evidence")
                if category == "missing_requirements" and evidence:
                    raise ValueError("Missing requirements cannot include resume evidence")
                if category == "resume_expression_issues" and item.confidence_level not in {
                    "strong",
                    "partial",
                }:
                    raise ValueError("Expression issues require grounded evidence")
                if category == "qualification_risks":
                    grounded_levels = {"strong", "partial"}
                    ungrounded_levels = {"missing", "uncertain"}
                    if evidence and item.confidence_level not in grounded_levels:
                        raise ValueError("Grounded risks require matching evidence level")
                    if not evidence and item.confidence_level not in ungrounded_levels:
                        raise ValueError("Ungrounded risks must be missing or uncertain")
        return payload

    @staticmethod
    def _normalize(value: str) -> str:
        return "".join(value.split()).casefold()

    def _record_failure(
        self,
        user: PublicUser,
        application_id: int,
        analysis_id: int,
        error_code: str,
        started: float,
    ) -> None:
        self.repository.fail_analysis(
            analysis_id, application_id, error_code, utc_now()
        )
        self._record_activity(
            user,
            application_id,
            "error",
            started,
            {"analysis_id": analysis_id, "error_code": error_code},
            error_code,
        )

    def _record_activity(
        self,
        user: PublicUser,
        application_id: int,
        status: str,
        started: float,
        metadata: dict[str, Any],
        error: str | None = None,
    ) -> None:
        self.workshop_repository.record_activity(
            user["id"],
            "career_match",
            f"application:{application_id}",
            "",
            status,
            int((time.perf_counter() - started) * 1000),
            utc_now(),
            error=error,
            metadata={
                "application_id": application_id,
                "provider": CAREER_PROVIDER,
                "model": CAREER_MODEL,
                "prompt_version": PROMPT_VERSION,
                **metadata,
            },
        )

    @staticmethod
    def _application_response(row: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": row["id"],
            "company_name": row["company_name"],
            "job_title": row["job_title"],
            "location": row["location"],
            "job_description": row["job_description"],
            "language": row["language"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "resume_source": {
                "source_type": row["source_type"],
                "original_filename": row["original_filename"],
                "extracted_text": row["extracted_text"],
                "parse_status": row["parse_status"],
                "parse_error": row["parse_error"],
            },
            "latest_analysis": None,
            "latest_analysis_error_code": None,
        }

    @staticmethod
    def _analysis_response(row: dict[str, Any] | None) -> dict[str, Any]:
        if row is None:
            raise RuntimeError("Analysis record was not found")
        grouped: dict[str, list[dict[str, Any]]] = {
            category: [] for category in CATEGORIES
        }
        for item in row["items"]:
            grouped[item["category"]].append(
                {
                    "jd_requirement": item["jd_requirement"],
                    "resume_evidence": item["resume_evidence"],
                    "explanation": item["explanation"],
                    "confidence_level": item["confidence_level"],
                }
            )
        return {
            "id": row["id"],
            "overall_alignment": row["overall_alignment"],
            **grouped,
            "summary": row["summary"],
            "analysis_limitations": json.loads(row["limitations"] or "[]"),
            "provider": row["provider"],
            "model": row["model"],
            "prompt_version": row["prompt_version"],
            "status": row["status"],
            "error_code": row["error_code"],
            "created_at": row["created_at"],
        }
