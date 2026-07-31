from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import require_user
from app.models.domain import PublicUser


router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/daily")
def daily_usage(
    request: Request,
    user: PublicUser = Depends(require_user),
) -> dict[str, Any]:
    return request.app.state.daily_usage_service.snapshot(user)
