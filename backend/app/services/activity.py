import time
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from app.models.domain import PublicUser
from app.repositories.workshop import WorkshopRepository
from app.services.auth import utc_now
from app.services.llm import LLMProvider


class ActivityService:
    def __init__(
        self, repository: WorkshopRepository, llm_provider: LLMProvider
    ) -> None:
        self.repository = repository
        self.llm_provider = llm_provider

    def run_llm(
        self,
        user: PublicUser,
        feature: str,
        input_preview: str,
        prompt: str,
        provider: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        return self._run_tracked(
            user,
            feature,
            input_preview,
            lambda: self.llm_provider.generate(prompt, provider),
            {**(metadata or {}), "provider": provider},
        )

    def _run_tracked(
        self,
        user: PublicUser,
        feature: str,
        input_preview: str,
        operation: Callable[[], str],
        metadata: dict[str, Any],
    ) -> dict[str, str]:
        started = time.perf_counter()
        try:
            result = operation()
            self._record(
                user,
                feature,
                input_preview,
                result,
                "success",
                started,
                metadata,
            )
            return {"reply": result, "result": result}
        except HTTPException as exc:
            self._record(
                user,
                feature,
                input_preview,
                "",
                "error",
                started,
                metadata,
                str(exc.detail),
            )
            raise
        except Exception as exc:
            message = "服务调用失败，请稍后重试"
            self._record(
                user,
                feature,
                input_preview,
                "",
                "error",
                started,
                metadata,
                message,
            )
            raise HTTPException(status_code=502, detail=message) from exc

    def _record(
        self,
        user: PublicUser,
        feature: str,
        input_preview: str,
        output_preview: str,
        status: str,
        started: float,
        metadata: dict[str, Any],
        error: str | None = None,
    ) -> None:
        self.repository.record_activity(
            user["id"],
            feature,
            input_preview,
            output_preview,
            status,
            int((time.perf_counter() - started) * 1000),
            utc_now(),
            error=error,
            metadata=metadata,
        )
