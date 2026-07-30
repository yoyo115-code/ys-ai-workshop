from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import require_admin
from app.models.domain import PublicUser


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def admin_users(
    request: Request, admin: PublicUser = Depends(require_admin)
) -> dict[str, Any]:
    del admin
    users = request.app.state.repository.list_admin_users()
    return {
        "users": users,
        "summary": {
            "total_users": len(users),
            "total_requests": sum(row["request_count"] for row in users),
            "total_errors": sum(row["error_count"] or 0 for row in users),
        },
    }


@router.get("/logs")
def admin_logs(
    request: Request,
    limit: int = 100,
    admin: PublicUser = Depends(require_admin),
) -> dict[str, Any]:
    del admin
    bounded_limit = max(1, min(limit, 500))
    return {"logs": request.app.state.repository.list_activity_logs(bounded_limit)}
