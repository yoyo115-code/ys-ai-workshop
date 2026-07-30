from typing import Any

from fastapi import APIRouter, Depends, Header, Request, status

from app.api.dependencies import require_user
from app.models.domain import PublicUser
from app.schemas.auth import LoginRequest, RegisterRequest


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(data: LoginRequest, request: Request) -> dict[str, Any]:
    return request.app.state.auth_service.login(data)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(data: RegisterRequest, request: Request) -> dict[str, Any]:
    return request.app.state.auth_service.register(data)


@router.post("/logout")
def logout(
    request: Request,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> dict[str, bool]:
    request.app.state.auth_service.logout(x_session_token)
    return {"ok": True}


@router.get("/me")
def me(user: PublicUser = Depends(require_user)) -> dict[str, Any]:
    return {"user": user}
