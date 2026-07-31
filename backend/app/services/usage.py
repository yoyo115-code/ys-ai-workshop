from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from app.core.config import Settings
from app.models.domain import PublicUser
from app.repositories.usage import DailyLimitExceeded, DailyUsageRepository


CAREER_ANALYSIS = "career_analysis"
SUGGESTION_GENERATION = "suggestion_generation"
SUGGESTION_REGENERATION = "suggestion_regeneration"
RESUME_EXPORT = "resume_export"


class DailyUsageService:
    def __init__(
        self,
        repository: DailyUsageRepository,
        settings: Settings,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    @property
    def limits(self) -> dict[str, int]:
        return {
            CAREER_ANALYSIS: self.settings.career_analysis_daily_limit,
            SUGGESTION_GENERATION: self.settings.suggestion_generation_daily_limit,
            SUGGESTION_REGENERATION: self.settings.suggestion_regeneration_daily_limit,
            RESUME_EXPORT: self.settings.resume_export_daily_limit,
        }

    def consume(self, user: PublicUser, usage_type: str) -> int | None:
        if usage_type not in self.limits:
            raise ValueError(f"Unknown usage type: {usage_type}")
        if self._is_exempt(user):
            return None
        now = self._utc_now()
        limit = self.limits[usage_type]
        try:
            used = self.repository.consume(
                user["id"], now.date().isoformat(), usage_type, limit, now.isoformat()
            )
        except DailyLimitExceeded as exc:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "daily_limit_exceeded",
                    "usage_type": usage_type,
                    "limit": limit,
                    "remaining": 0,
                    "resets_at": self._next_reset(now),
                    "message": "今日额度已用完，请在 UTC 日期重置后重试",
                },
            ) from exc
        return max(limit - used, 0)

    def snapshot(self, user: PublicUser) -> dict[str, Any]:
        now = self._utc_now()
        exempt = self._is_exempt(user)
        counts = (
            {}
            if exempt
            else self.repository.counts(user["id"], now.date().isoformat())
        )
        quotas: dict[str, dict[str, int | bool | None]] = {}
        for usage_type, limit in self.limits.items():
            used = 0 if exempt else counts.get(usage_type, 0)
            quotas[usage_type] = {
                "limit": None if exempt else limit,
                "used": used,
                "remaining": None if exempt else max(limit - used, 0),
                "unlimited": exempt,
            }
        return {
            "usage_date": now.date().isoformat(),
            "timezone": "UTC",
            "resets_at": self._next_reset(now),
            "admin_exempt": exempt,
            "quotas": quotas,
        }

    def _is_exempt(self, user: PublicUser) -> bool:
        return user["role"] == "admin" and self.settings.admin_daily_limit_exempt

    def _utc_now(self) -> datetime:
        now = self.now_provider()
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    @staticmethod
    def _next_reset(now: datetime) -> str:
        next_day = datetime.combine(
            now.date() + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc
        )
        return next_day.isoformat()
