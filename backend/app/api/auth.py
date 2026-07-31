from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response, status

from app.api.dependencies import require_user, session_token_from_request
from app.core.config import Settings
from app.models.domain import PublicUser
from app.schemas.auth import DeleteAccountRequest, LoginRequest, RegisterRequest


router = APIRouter(prefix="/auth", tags=["auth"])


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_hours * 60 * 60,
        expires=datetime.now(timezone.utc) + timedelta(hours=settings.session_hours),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def auth_response(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    if settings.is_production:
        return {"user": payload["user"]}
    return payload


@router.post("/login")
def login(data: LoginRequest, request: Request, response: Response) -> dict[str, Any]:
    payload = request.app.state.auth_service.login(data)
    settings = request.app.state.settings
    set_session_cookie(response, payload["token"], settings)
    return auth_response(payload, settings)


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterRequest, request: Request, response: Response
) -> dict[str, Any]:
    payload = request.app.state.auth_service.register(data)
    settings = request.app.state.settings
    set_session_cookie(response, payload["token"], settings)
    return auth_response(payload, settings)


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> dict[str, bool]:
    token = session_token_from_request(request, x_session_token)
    request.app.state.auth_service.logout(token)
    clear_session_cookie(response, request.app.state.settings)
    return {"ok": True}


@router.get("/me")
def me(user: PublicUser = Depends(require_user)) -> dict[str, Any]:
    return {"user": user}


@router.delete("/account", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    data: DeleteAccountRequest,
    request: Request,
    response: Response,
    user: PublicUser = Depends(require_user),
) -> Response:
    request.app.state.privacy_service.delete_account(user, data.password)
    clear_session_cookie(response, request.app.state.settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
