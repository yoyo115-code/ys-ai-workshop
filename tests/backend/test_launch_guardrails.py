import json
import os
import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import yaml
from fastapi import HTTPException
from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings, get_settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.usage import (  # noqa: E402
    CAREER_ANALYSIS,
    RESUME_EXPORT,
    SUGGESTION_GENERATION,
    SUGGESTION_REGENERATION,
)


class GuardrailProvider:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.providers: list[str] = []

    def generate(self, prompt: str, provider: str) -> str:
        self.providers.append(provider)
        if self.fail:
            raise RuntimeError("synthetic provider failure")
        if "SECURITY AND EVIDENCE RULES" in prompt:
            return json.dumps(
                {
                    "overall_alignment": "insufficient_evidence",
                    "covered_requirements": [],
                    "partially_covered_requirements": [],
                    "missing_requirements": [],
                    "uncertain_requirements": [],
                    "resume_expression_issues": [],
                    "qualification_risks": [],
                    "summary": "Synthetic grounded result.",
                    "analysis_limitations": ["Synthetic test only."],
                }
            )
        return "synthetic"


class LaunchGuardrailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "guardrails.db"
        self.provider = GuardrailProvider()
        self.settings = self._settings()
        self.client_context = TestClient(create_app(self.settings, self.provider))
        self.client = self.client_context.__enter__()
        self.password = "LaunchGuard123"

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary_directory.cleanup()
        get_settings.cache_clear()

    def _settings(self, **overrides) -> Settings:
        values = {
            "app_env": "test",
            "database_url": f"sqlite:///{self.database_path}",
            "frontend_dir": PROJECT_ROOT / "frontend",
            "schema_path": PROJECT_ROOT / "database" / "schema.sql",
            "resume_export_dir": self.root / "exports",
            "session_secret": "synthetic-launch-session-secret",
        }
        values.update(overrides)
        return Settings(**values)

    def register(self, client: TestClient | None = None, username: str = "launch_user") -> dict:
        active_client = client or self.client
        response = active_client.post(
            "/auth/register",
            json={
                "username": username,
                "password": self.password,
                "display_name": "Launch User",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    @staticmethod
    def headers(token: str) -> dict[str, str]:
        return {"X-Session-Token": token}

    def create_application(self, client: TestClient, token: str) -> dict:
        response = client.post(
            "/career/applications",
            headers=self.headers(token),
            data={
                "resume_text": "Built Python services.",
                "job_description": "Requires Python services.",
                "language": "en",
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def production_client(
        self, provider: GuardrailProvider | None = None
    ) -> tuple[TestClient, TestClient]:
        path = self.root / f"production-{len(list(self.root.glob('production-*.db')))}.db"
        settings = self._settings(
            app_env="production",
            database_url=f"sqlite:///{path}",
            ai_labs_enabled=False,
            primary_llm_provider="deepseek",
            session_cookie_secure=True,
            session_secret="synthetic-production-session-secret-12345",
        )
        with patch.object(Settings, "production_configuration_errors", return_value=()):
            application = create_app(settings, provider or GuardrailProvider())
        context = TestClient(application, base_url="https://beta.invalid")
        return context, context.__enter__()

    def test_production_defaults_disable_labs_and_select_deepseek(self) -> None:
        with patch.dict("os.environ", {"APP_ENV": "production"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
        self.assertFalse(settings.ai_labs_enabled)
        self.assertEqual(settings.primary_llm_provider, "deepseek")
        self.assertTrue(settings.session_cookie_secure)

    def test_production_does_not_require_anthropic_key(self) -> None:
        settings = Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:placeholder@db/workshop",
            storage_backend="s3",
            s3_bucket="private",
            s3_region="auto",
            s3_access_key_id="synthetic",
            s3_secret_access_key="synthetic",
            deepseek_api_key="synthetic",
            session_secret="synthetic-session-secret-1234567890",
            cors_origins=("https://beta.invalid",),
            registration_mode="invite_only",
            ai_labs_enabled=False,
            session_cookie_secure=True,
        )
        settings.validate()
        self.assertEqual(settings.anthropic_api_key, "")

    def test_production_ai_labs_return_feature_disabled(self) -> None:
        context, client = self.production_client()
        self.addCleanup(context.__exit__, None, None, None)
        self.register(client)
        response = client.post("/resume", json={"text": "synthetic"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"]["code"], "feature_disabled")
        self.assertFalse(client.get("/config/public").json()["ai_labs_enabled"])

    def test_career_uses_only_deepseek_without_fallback(self) -> None:
        provider = GuardrailProvider(fail=True)
        context, client = self.production_client(provider)
        self.addCleanup(context.__exit__, None, None, None)
        self.register(client)
        application = client.post(
            "/career/applications",
            data={
                "resume_text": "Built Python services.",
                "job_description": "Requires Python services.",
                "language": "en",
            },
        ).json()
        response = client.post(f"/career/applications/{application['id']}/analyze")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(provider.providers, ["deepseek"])

    def test_four_daily_limits_are_enforced(self) -> None:
        payload = self.register()
        user = payload["user"]
        service = self.client.app.state.daily_usage_service
        for usage_type, limit in service.limits.items():
            for _ in range(limit):
                service.consume(user, usage_type)
            with self.subTest(usage_type=usage_type):
                with self.assertRaises(HTTPException) as raised:
                    service.consume(user, usage_type)
                self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(
            set(service.limits),
            {
                CAREER_ANALYSIS,
                SUGGESTION_GENERATION,
                SUGGESTION_REGENERATION,
                RESUME_EXPORT,
            },
        )

    def test_daily_limits_reset_on_utc_date(self) -> None:
        user = self.register()["user"]
        service = self.client.app.state.daily_usage_service
        current = [datetime(2026, 7, 31, 23, 59, tzinfo=timezone.utc)]
        service.now_provider = lambda: current[0]
        service.consume(user, CAREER_ANALYSIS)
        current[0] = datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc)
        snapshot = service.snapshot(user)
        self.assertEqual(snapshot["usage_date"], "2026-08-01")
        self.assertEqual(snapshot["quotas"][CAREER_ANALYSIS]["remaining"], 2)

    def test_concurrent_daily_limit_cannot_be_exceeded(self) -> None:
        user = self.register()["user"]
        service = self.client.app.state.daily_usage_service
        barrier = Barrier(8)

        def consume_once(_: int) -> str:
            barrier.wait()
            try:
                service.consume(user, CAREER_ANALYSIS)
                return "accepted"
            except HTTPException as exc:
                self.assertEqual(exc.status_code, 429)
                return "limited"

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(consume_once, range(8)))
        self.assertEqual(results.count("accepted"), 2)
        self.assertEqual(results.count("limited"), 6)

    def test_invalid_or_oversized_input_does_not_consume_quota(self) -> None:
        path = self.root / "short-input.db"
        settings = self._settings(
            database_url=f"sqlite:///{path}",
            max_resume_characters=10,
            max_job_description_characters=10,
        )
        with TestClient(create_app(settings, GuardrailProvider())) as client:
            token = self.register(client, "short_user")["token"]
            for resume, jd in (("x" * 11, "valid"), ("valid", "x" * 11), ("valid", "")):
                response = client.post(
                    "/career/applications",
                    headers=self.headers(token),
                    data={"resume_text": resume, "job_description": jd, "language": "en"},
                )
                self.assertEqual(response.status_code, 422)
            usage = client.get("/usage/daily", headers=self.headers(token)).json()
        self.assertEqual(usage["quotas"][CAREER_ANALYSIS]["used"], 0)

    def test_production_cookie_is_secure_httponly_and_lax(self) -> None:
        context, client = self.production_client()
        self.addCleanup(context.__exit__, None, None, None)
        response = client.post(
            "/auth/register",
            json={
                "username": "cookie_user",
                "password": self.password,
                "display_name": "Cookie User",
            },
        )
        cookie = response.headers["set-cookie"]
        self.assertNotIn("token", response.json())
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        self.assertIn("SameSite=lax", cookie)
        self.assertIn("Max-Age=43200", cookie)
        self.assertEqual(client.get("/auth/me").status_code, 200)

    def test_production_rejects_header_session(self) -> None:
        context, client = self.production_client()
        self.addCleanup(context.__exit__, None, None, None)
        self.register(client, "header_user")
        database_path = client.app.state.database.sqlite_path
        with sqlite3.connect(database_path) as connection:
            token = connection.execute("SELECT token FROM sessions").fetchone()[0]
        client.cookies.clear()
        response = client.get("/auth/me", headers=self.headers(token))
        self.assertEqual(response.status_code, 401)

    def test_local_cookie_and_header_compatibility(self) -> None:
        response = self.client.post(
            "/auth/register",
            json={
                "username": "local_cookie",
                "password": self.password,
                "display_name": "Local Cookie",
            },
        )
        cookie = response.headers["set-cookie"]
        token = response.json()["token"]
        self.assertIn("HttpOnly", cookie)
        self.assertNotIn("Secure", cookie)
        self.client.cookies.clear()
        self.assertEqual(
            self.client.get("/auth/me", headers=self.headers(token)).status_code, 200
        )

    def test_login_and_logout_set_and_clear_cookie(self) -> None:
        self.register(username="session_user")
        self.client.cookies.clear()
        login = self.client.post(
            "/auth/login",
            json={"username": "session_user", "password": self.password},
        )
        self.assertIn("ys_ai_session=", login.headers["set-cookie"])
        self.assertTrue(self.client.get("/config/public").json()["session_active"])
        logout = self.client.post("/auth/logout")
        self.assertIn("Max-Age=0", logout.headers["set-cookie"])
        self.assertFalse(self.client.get("/config/public").json()["session_active"])
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_render_blueprint_uses_current_contract(self) -> None:
        blueprint = yaml.safe_load((PROJECT_ROOT / "render.yaml").read_text())
        service = blueprint["services"][0]
        self.assertEqual(service["runtime"], "docker")
        self.assertEqual(service["plan"], "starter")
        self.assertEqual(service["region"], "singapore")
        self.assertEqual(service["branch"], "main")
        self.assertEqual(service["dockerfilePath"], "./Dockerfile")
        self.assertEqual(service["healthCheckPath"], "/health/ready")
        self.assertEqual(service["autoDeployTrigger"], "checksPass")
        self.assertEqual(service["preDeployCommand"], "alembic upgrade head")
        self.assertNotIn("env", service)
        env = {item["key"]: item for item in service["envVars"]}
        self.assertEqual(
            env["DATABASE_URL"]["fromDatabase"],
            {"name": "ys-ai-workshop-db", "property": "connectionString"},
        )
        self.assertTrue(env["SESSION_SECRET"]["generateValue"])
        self.assertNotIn("ANTHROPIC_API_KEY", env)

    def test_render_secrets_and_r2_values_are_private(self) -> None:
        blueprint = yaml.safe_load((PROJECT_ROOT / "render.yaml").read_text())
        env = {item["key"]: item for item in blueprint["services"][0]["envVars"]}
        manual = {
            "S3_ENDPOINT_URL",
            "S3_BUCKET_NAME",
            "S3_REGION",
            "S3_ACCESS_KEY_ID",
            "S3_SECRET_ACCESS_KEY",
            "DEEPSEEK_API_KEY",
            "INITIAL_ADMIN_USERNAME",
            "INITIAL_ADMIN_PASSWORD",
            "CORS_ORIGINS",
        }
        self.assertTrue(all(env[name] == {"key": name, "sync": False} for name in manual))
        self.assertLessEqual(int(env["S3_PRESIGNED_URL_SECONDS"]["value"]), 600)
        database = blueprint["databases"][0]
        self.assertEqual(database["name"], "ys-ai-workshop-db")
        self.assertEqual(database["plan"], "basic-256mb")
        self.assertEqual(database["region"], "singapore")

    def test_production_configuration_requires_launch_guards(self) -> None:
        base = dict(
            app_env="production",
            database_url="postgresql+psycopg://user:placeholder@db/workshop",
            storage_backend="s3",
            s3_bucket="private",
            s3_region="auto",
            s3_access_key_id="synthetic",
            s3_secret_access_key="synthetic",
            deepseek_api_key="synthetic",
            session_secret="synthetic-session-secret-1234567890",
            cors_origins=("https://beta.invalid",),
            registration_mode="invite_only",
        )
        with self.assertRaisesRegex(RuntimeError, "AI_LABS_ENABLED"):
            Settings(**base, session_cookie_secure=True).validate()
        with self.assertRaisesRegex(RuntimeError, "SESSION_COOKIE_SECURE"):
            Settings(**base, ai_labs_enabled=False).validate()
        with self.assertRaisesRegex(RuntimeError, "PRIMARY_LLM_PROVIDER"):
            Settings(
                **base,
                ai_labs_enabled=False,
                session_cookie_secure=True,
                primary_llm_provider="anthropic",
            ).validate()

    def test_presigned_urls_cannot_exceed_ten_minutes(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "must not exceed 600"):
            Settings(s3_presigned_url_seconds=601).validate()

    def test_frontend_hides_labs_and_never_persists_session_token(self) -> None:
        html = (PROJECT_ROOT / "frontend" / "index.html").read_text()
        script = (PROJECT_ROOT / "frontend" / "assets" / "js" / "app.js").read_text()
        self.assertIn("data-ai-lab-nav", html)
        self.assertIn('id="daily-usage-summary"', html)
        self.assertIn("applyAiLabsAvailability", script)
        self.assertNotIn("localStorage", script)
        self.assertNotIn("X-Session-Token", script)

    def test_docker_binds_to_render_port(self) -> None:
        dockerfile = (PROJECT_ROOT / "Dockerfile").read_text()
        self.assertIn("--host 0.0.0.0", dockerfile)
        self.assertIn("${PORT:-8000}", dockerfile)


if __name__ == "__main__":
    unittest.main()
