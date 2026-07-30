import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"

load_dotenv(PROJECT_ROOT / ".env")


def _parse_origins(value: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


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
    return Settings(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
        initial_admin_username=os.getenv("INITIAL_ADMIN_USERNAME", "").strip().lower(),
        initial_admin_password=os.getenv("INITIAL_ADMIN_PASSWORD", ""),
        database_url=os.getenv("DATABASE_URL", "sqlite:///./platform.db").strip()
        or "sqlite:///./platform.db",
        cors_origins=_parse_origins(os.getenv("CORS_ORIGINS", "")),
    )
