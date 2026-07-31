from fastapi import Depends, Header, HTTPException, Request

from app.models.domain import PublicUser


def require_ai_labs_enabled(request: Request) -> None:
    if request.app.state.settings.ai_labs_enabled:
        return
    raise HTTPException(
        status_code=403,
        detail={
            "code": "feature_disabled",
            "message": "AI Labs are disabled for this Private Beta environment",
        },
    )


def session_token_from_request(
    request: Request, x_session_token: str | None = None
) -> str | None:
    settings = request.app.state.settings
    cookie_token = request.cookies.get(settings.session_cookie_name)
    if settings.is_production:
        return cookie_token
    return x_session_token or cookie_token


def require_user(
    request: Request,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> PublicUser:
    token = session_token_from_request(request, x_session_token)
    user = request.app.state.auth_service.current_user(token)
    if user is None:
        detail = "请先登录" if not token else "登录已失效，请重新登录"
        raise HTTPException(status_code=401, detail=detail)
    return user


def require_admin(user: PublicUser = Depends(require_user)) -> PublicUser:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    return user
