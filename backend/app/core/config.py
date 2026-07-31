import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"
DEFAULT_RESUME_EXPORT_DIR = BACKEND_DIR / "generated" / "resume_exports"

load_dotenv(PROJECT_ROOT / ".env")


def _parse_origins(value: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


def _positive_int(value: str, default: int) -> int:
    try:
        parsed = int(value)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    deepseek_api_key: str = ""
    anthropic_api_key: str = ""
    initial_admin_username: str = ""
    initial_admin_password: str = ""
    database_url: str = "sqlite:///./platform.db"
    cors_origins: tuple[str, ...] = ()
    frontend_dir: Path = FRONTEND_DIR
    schema_path: Path = SCHEMA_PATH
    max_upload_bytes: int = 20 * 1024 * 1024
    session_hours: int = 12
    llm_timeout_seconds: int = 45
    llm_max_retries: int = 2
    resume_export_dir: Path = DEFAULT_RESUME_EXPORT_DIR
    storage_backend: str = "local"
    s3_endpoint_url: str = ""
    s3_bucket: str = ""
    s3_region: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    s3_presigned_url_seconds: int = 300
    registration_mode: str = "open"
    export_retention_days: int = 7
    session_secret: str = ""

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def database_path(self) -> Path:
        url = self.database_url or "sqlite:///./platform.db"
        prefix = "sqlite:///"
        if not url.startswith(prefix):
            raise RuntimeError("Only sqlite:/// DATABASE_URL values are supported")
        raw_path = url[len(prefix) :]
        path = Path(raw_path)
        if not path.is_absolute():
            path = BACKEND_DIR / path
        return path.resolve()

    def production_configuration_errors(self) -> tuple[str, ...]:
        if not self.is_production:
            return ()
        missing: list[str] = []
        if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            missing.append("DATABASE_URL (PostgreSQL required)")
        if self.storage_backend != "s3":
            missing.append("STORAGE_PROVIDER (s3 required)")
        for name, value in (
            ("S3_BUCKET_NAME", self.s3_bucket),
            ("S3_REGION", self.s3_region),
            ("S3_ACCESS_KEY_ID", self.s3_access_key_id),
            ("S3_SECRET_ACCESS_KEY", self.s3_secret_access_key),
            ("DEEPSEEK_API_KEY", self.deepseek_api_key),
            ("ANTHROPIC_API_KEY", self.anthropic_api_key),
            ("SESSION_SECRET", self.session_secret),
        ):
            if not value:
                missing.append(name)
        if not self.cors_origins:
            missing.append("CORS_ORIGINS")
        if self.registration_mode != "invite_only":
            missing.append("REGISTRATION_MODE (invite_only required)")
        return tuple(missing)

    def validate(self) -> None:
        if self.app_env not in {"development", "test", "production"}:
            raise RuntimeError("APP_ENV must be development, test, or production")
        if self.storage_backend not in {"local", "s3"}:
            raise RuntimeError("STORAGE_PROVIDER must be local or s3")
        if self.registration_mode not in {"open", "invite_only", "disabled"}:
            raise RuntimeError(
                "REGISTRATION_MODE must be open, invite_only, or disabled"
            )
        if bool(self.initial_admin_username) != bool(self.initial_admin_password):
            raise RuntimeError(
                "INITIAL_ADMIN_USERNAME and INITIAL_ADMIN_PASSWORD must be configured together"
            )
        if self.is_production and self.session_secret and len(self.session_secret) < 32:
            raise RuntimeError("SESSION_SECRET must contain at least 32 characters")
        if self.is_production and "*" in self.cors_origins:
            raise RuntimeError("CORS_ORIGINS must not use a wildcard in production")
        errors = self.production_configuration_errors()
        if errors:
            raise RuntimeError(
                "Production configuration is incomplete: " + ", ".join(errors)
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    app_env = os.getenv("APP_ENV", "development").strip().lower() or "development"
    export_dir_value = os.getenv("RESUME_EXPORT_DIR", "").strip()
    export_dir = Path(export_dir_value) if export_dir_value else DEFAULT_RESUME_EXPORT_DIR
    if not export_dir.is_absolute():
        export_dir = BACKEND_DIR / export_dir
    return Settings(
        app_env=app_env,
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        initial_admin_username=os.getenv("INITIAL_ADMIN_USERNAME", "").strip().lower(),
        initial_admin_password=os.getenv("INITIAL_ADMIN_PASSWORD", ""),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./platform.db").strip()
        or "sqlite:///./platform.db",
        cors_origins=_parse_origins(os.getenv("CORS_ORIGINS", "")),
        llm_timeout_seconds=_positive_int(
            os.getenv("LLM_TIMEOUT_SECONDS", "45"), 45
        ),
        llm_max_retries=_positive_int(os.getenv("LLM_MAX_RETRIES", "2"), 2),
        resume_export_dir=export_dir.resolve(),
        storage_backend=(
            os.getenv(
                "STORAGE_PROVIDER",
                os.getenv(
                    "STORAGE_BACKEND",
                    "s3" if app_env == "production" else "local",
                ),
            )
            .strip()
            .lower()
            or ("s3" if app_env == "production" else "local")
        ),
        s3_endpoint_url=os.getenv("S3_ENDPOINT_URL", "").strip(),
        s3_bucket=os.getenv("S3_BUCKET_NAME", os.getenv("S3_BUCKET", "")).strip(),
        s3_region=os.getenv("S3_REGION", "").strip(),
        s3_access_key_id=os.getenv("S3_ACCESS_KEY_ID", "").strip(),
        s3_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY", ""),
        s3_presigned_url_seconds=_positive_int(
            os.getenv("S3_PRESIGNED_URL_SECONDS", "300"), 300
        ),
        registration_mode=(
            os.getenv(
                "REGISTRATION_MODE", "invite_only" if app_env == "production" else "open"
            )
            .strip()
            .lower()
            or ("invite_only" if app_env == "production" else "open")
        ),
        export_retention_days=_positive_int(
            os.getenv("EXPORT_RETENTION_DAYS", "7"), 7
        ),
        session_secret=os.getenv("SESSION_SECRET", ""),
    )
