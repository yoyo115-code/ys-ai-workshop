from fastapi import Depends, Header, HTTPException, Request

from app.models.domain import PublicUser


def require_user(
    request: Request,
    x_session_token: str | None = Header(default=None, alias="X-Session-Token"),
) -> PublicUser:
    user = request.app.state.auth_service.current_user(x_session_token)
    if user is None:
        detail = "请先登录" if not x_session_token else "登录已失效，请重新登录"
        raise HTTPException(status_code=401, detail=detail)
    return user


def require_admin(user: PublicUser = Depends(require_user)) -> PublicUser:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    return user
