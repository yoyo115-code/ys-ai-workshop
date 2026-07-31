import io
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402


def alembic_config(output_buffer=None) -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"), output_buffer=output_buffer)
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return config


class MigrationTests(unittest.TestCase):
    def tearDown(self) -> None:
        get_settings.cache_clear()

    def test_alembic_upgrades_empty_sqlite_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "migration.db"
            with patch.dict(
                os.environ,
                {"APP_ENV": "test", "DATABASE_URL": f"sqlite:///{path}"},
                clear=False,
            ):
                get_settings.cache_clear()
                command.upgrade(alembic_config(), "head")
            with sqlite3.connect(path) as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table'"
                    )
                }
                revision = connection.execute(
                    "SELECT version_num FROM alembic_version"
                ).fetchone()[0]
        self.assertIn("resume_exports", tables)
        self.assertIn("invite_codes", tables)
        self.assertIn("daily_usage", tables)
        self.assertEqual(revision, "20260731_03")

    def test_postgresql_offline_migration_has_no_sqlite_statements(self) -> None:
        output = io.StringIO()
        with patch.dict(
            os.environ,
            {
                "APP_ENV": "test",
                "DATABASE_URL": "postgresql+psycopg://user:placeholder@localhost/workshop",
            },
            clear=False,
        ):
            get_settings.cache_clear()
            command.upgrade(alembic_config(output), "head", sql=True)
        sql = output.getvalue()
        self.assertIn("CREATE TABLE invite_codes", sql)
        self.assertIn("CREATE TABLE daily_usage", sql)
        self.assertNotIn("PRAGMA", sql)
        self.assertNotIn("AUTOINCREMENT", sql)

    def test_sqlite_incremental_migration_declares_hashed_invites(self) -> None:
        migration = (
            PROJECT_ROOT / "database" / "migrations" / "0004_private_beta.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("code_hash", migration)
        self.assertNotIn("plaintext", migration.lower())
        self.assertIn("expires_at", migration)

    def test_daily_usage_migration_has_atomic_identity(self) -> None:
        migration = (
            PROJECT_ROOT / "database" / "migrations" / "0005_launch_guardrails.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("PRIMARY KEY (user_id, usage_date, usage_type)", migration)
        self.assertIn("used_count", migration)


if __name__ == "__main__":
    unittest.main()
