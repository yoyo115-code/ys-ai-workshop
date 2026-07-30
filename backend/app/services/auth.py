import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException

from app.core.config import Settings
from app.core.security import (
    hash_password,
    new_password_salt,
    new_session_token,
    validate_display_name,
    validate_password,
    validate_username,
    verify_password,
)
from app.models.domain import PublicUser
from app.repositories.workshop import WorkshopRepository
from app.schemas.auth import LoginRequest, RegisterRequest


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def public_user(row: sqlite3.Row) -> PublicUser:
    return {
        "id": row["id"],
        "username": row["username"],
        "display_name": row["display_name"],
        "role": row["role"],
    }


class AuthService:
    def __init__(self, repository: WorkshopRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def initialize(self) -> None:
        self.repository.delete_expired_sessions(utc_now())
        username = self.settings.initial_admin_username
        password = self.settings.initial_admin_password
        if bool(username) != bool(password):
            raise RuntimeError(
                "INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD must be configured together"
            )
        if not username:
            return
        try:
            validate_username(username)
            validate_password(password)
        except ValueError as exc:
            raise RuntimeError(f"Invalid initial administrator configuration: {exc}") from exc
        salt = new_password_salt()
        self.repository.create_user_if_absent(
            username,
            hash_password(password, salt),
            salt,
            "Administrator",
            "admin",
            utc_now(),
        )

    def login(self, data: LoginRequest) -> dict[str, Any]:
        username = data.username.strip().lower()
        row = self.repository.find_active_user_by_username(username)
        if row is None or not verify_password(
            data.password, row["salt"], row["password_hash"]
        ):
            raise HTTPException(status_code=401, detail="账号或密码错误")
        token = new_session_token()
        now = utc_now()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(hours=self.settings.session_hours)
        ).isoformat()
        self.repository.create_session(token, row["id"], now, expires_at)
        return {"token": token, "user": public_user(row)}

    def register(self, data: RegisterRequest) -> dict[str, Any]:
        username = data.username.strip().lower()
        display_name = data.display_name.strip()
        try:
            validate_username(username)
            validate_display_name(display_name)
            validate_password(data.password)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        salt = new_password_salt()
        now = utc_now()
        try:
            row = self.repository.create_user(
                username,
                hash_password(data.password, salt),
                salt,
                display_name,
                now,
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="该账号已被注册") from exc

        token = new_session_token()
        expires_at = (
            datetime.now(timezone.utc) + timedelta(hours=self.settings.session_hours)
        ).isoformat()
        self.repository.create_session(token, row["id"], now, expires_at)
        return {"token": token, "user": public_user(row)}

    def logout(self, token: str | None) -> None:
        if token:
            self.repository.delete_session(token)

    def current_user(self, token: str | None) -> PublicUser | None:
        if not token:
            return None
        row = self.repository.find_user_by_session(token, utc_now())
        return public_user(row) if row is not None else None
