import hashlib
import hmac
import re
import secrets


def hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt), 200_000
    ).hex()


def verify_password(password: str, salt: str, expected_hash: str) -> bool:
    return hmac.compare_digest(expected_hash, hash_password(password, salt))


def new_password_salt() -> str:
    return secrets.token_hex(16)


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def new_invite_code() -> str:
    return secrets.token_urlsafe(24)


def hash_invite_code(invite_code: str, session_secret: str) -> str:
    if not session_secret:
        raise ValueError("SESSION_SECRET is required for invitation codes")
    return hmac.new(
        session_secret.encode("utf-8"),
        invite_code.strip().encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def validate_username(username: str) -> None:
    if not re.fullmatch(r"[a-z0-9_]{3,32}", username):
        raise ValueError("账号需为 3-32 位小写字母、数字或下划线")


def validate_password(password: str) -> None:
    if not 8 <= len(password) <= 128:
        raise ValueError("密码需为 8-128 个字符")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("密码必须同时包含字母和数字")


def validate_display_name(display_name: str) -> None:
    if not 1 <= len(display_name) <= 30:
        raise ValueError("姓名需为 1-30 个字符")
