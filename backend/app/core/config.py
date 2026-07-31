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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    export_dir_value = os.getenv("RESUME_EXPORT_DIR", "").strip()
    export_dir = Path(export_dir_value) if export_dir_value else DEFAULT_RESUME_EXPORT_DIR
    if not export_dir.is_absolute():
        export_dir = BACKEND_DIR / export_dir
    return Settings(
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
    )
