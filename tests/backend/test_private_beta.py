import sqlite3
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.cli.create_invite import build_parser  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.core.security import (  # noqa: E402
    hash_invite_code,
    hash_password,
    new_password_salt,
)
from app.main import create_app  # noqa: E402
from app.repositories.database import CompatConnection  # noqa: E402
from app.repositories.workshop import InviteCodeError  # noqa: E402
from app.services.storage import (  # noqa: E402
    LocalStorageProvider,
    S3StorageProvider,
    StorageError,
)


class BetaMockProvider:
    def generate(self, prompt: str, provider: str) -> str:
        return "synthetic mock response"


class FakeBody:
    def __init__(self, value: bytes) -> None:
        self.value = value

    def read(self) -> bytes:
        return self.value


class FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.bucket_checks = 0

    def put_object(self, Bucket: str, Key: str, Body: bytes) -> None:
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": FakeBody(self.objects[(Bucket, Key)])}

    def delete_object(self, Bucket: str, Key: str) -> None:
        self.objects.pop((Bucket, Key), None)

    def head_object(self, Bucket: str, Key: str) -> None:
        if (Bucket, Key) not in self.objects:
            raise KeyError(Key)

    def head_bucket(self, Bucket: str) -> None:
        self.bucket_checks += 1

    def generate_presigned_url(self, action: str, Params: dict, ExpiresIn: int) -> str:
        return f"https://storage.invalid/{Params['Key']}?expires={ExpiresIn}"


class PrivateBetaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.database_path = self.root / "private-beta.db"
        self.export_dir = self.root / "exports"
        self.settings = Settings(
            app_env="test",
            database_url=f"sqlite:///{self.database_path}",
            frontend_dir=PROJECT_ROOT / "frontend",
            schema_path=PROJECT_ROOT / "database" / "schema.sql",
            resume_export_dir=self.export_dir,
            session_secret="synthetic-session-secret-for-tests",
        )
        self.client_context = TestClient(
            create_app(self.settings, BetaMockProvider())
        )
        self.client = self.client_context.__enter__()
        self.password = "PrivateBeta123"

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary_directory.cleanup()

    @staticmethod
    def headers(token: str, json: bool = False) -> dict[str, str]:
        result = {"X-Session-Token": token}
        if json:
            result["Content-Type"] = "application/json"
        return result

    def register(self, username: str = "beta_user") -> dict:
        response = self.client.post(
            "/auth/register",
            json={
                "username": username,
                "display_name": "Beta User",
                "password": self.password,
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def workspace(self, token: str) -> tuple[dict, dict]:
        application = self.client.post(
            "/career/applications",
            headers=self.headers(token),
            data={
                "resume_text": "Beta User\nEXPERIENCE\nAnalyst\nExample Co\n- Built Python tools.",
                "job_description": "Requires Python experience.",
                "company_name": "Example Co",
                "job_title": "Analyst",
                "language": "en",
            },
        ).json()
        workspace = self.client.get(
            f"/career/applications/{application['id']}/resume-suggestions",
            headers=self.headers(token),
        ).json()
        return application, workspace

    def export(self, token: str, version_id: int) -> dict:
        renderer = self.client.app.state.resume_export_service.renderer

        def render(*args, **kwargs):
            output_path = args[-1]
            output_path.write_bytes(b"synthetic-docx")

        with patch.object(renderer, "render", side_effect=render):
            response = self.client.post(
                f"/career/resume-versions/{version_id}/exports",
                headers=self.headers(token, True),
                json={"format": "docx", "template_key": "minimal_ats"},
            )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def invite_client(
        self, *, max_uses: int = 1, expires_delta: timedelta = timedelta(days=1)
    ) -> tuple[TestClient, str, Path]:
        path = self.root / f"invite-{len(list(self.root.glob('invite-*.db')))}.db"
        settings = Settings(
            app_env="test",
            database_url=f"sqlite:///{path}",
            frontend_dir=PROJECT_ROOT / "frontend",
            schema_path=PROJECT_ROOT / "database" / "schema.sql",
            resume_export_dir=self.root / "invite-exports",
            registration_mode="invite_only",
            session_secret="invite-test-secret",
        )
        context = TestClient(create_app(settings, BetaMockProvider()))
        client = context.__enter__()
        self.addCleanup(context.__exit__, None, None, None)
        repository = client.app.state.repository
        salt = new_password_salt()
        now = datetime.now(timezone.utc)
        repository.create_user_if_absent(
            "beta_admin",
            hash_password("AdminPassword123", salt),
            salt,
            "Beta Admin",
            "admin",
            now.isoformat(),
        )
        admin = repository.find_active_admin("beta_admin")
        code = "synthetic-private-beta-invite"
        repository.create_invite(
            hash_invite_code(code, settings.session_secret),
            max_uses,
            (now + expires_delta).isoformat(),
            admin["id"],
            now.isoformat(),
        )
        return client, code, path

    def test_liveness(self) -> None:
        self.assertEqual(self.client.get("/health/live").json(), {"status": "ok"})

    def test_readiness_checks_database_and_storage(self) -> None:
        response = self.client.get("/health/ready")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["checks"],
            {"configuration": "ok", "database": "ok", "storage": "ok"},
        )

    def test_readiness_fails_without_leaking_details(self) -> None:
        with patch.object(self.client.app.state.storage_provider, "healthcheck", return_value=False):
            response = self.client.get("/health/ready")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn(str(self.export_dir), response.text)

    def test_public_configuration_is_non_secret(self) -> None:
        response = self.client.get("/config/public")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["registration_mode"], "open")
        self.assertFalse(response.json()["session_active"])
        self.assertNotIn("secret", response.text.lower())

    def test_production_configuration_rejects_sqlite_fallback(self) -> None:
        settings = Settings(app_env="production", database_url="sqlite:///fallback.db")
        with self.assertRaisesRegex(RuntimeError, "PostgreSQL required"):
            settings.validate()

    def test_production_configuration_error_does_not_include_values(self) -> None:
        value = "do-not-leak-this-value"
        settings = Settings(app_env="production", session_secret=value)
        with self.assertRaises(RuntimeError) as raised:
            settings.validate()
        self.assertNotIn(value, str(raised.exception))

    def test_valid_production_configuration(self) -> None:
        settings = Settings(
            app_env="production",
            database_url="postgresql+psycopg://user:placeholder@db/workshop",
            storage_backend="s3",
            s3_bucket="private-bucket",
            s3_region="test-region",
            s3_access_key_id="synthetic-id",
            s3_secret_access_key="synthetic-secret",
            deepseek_api_key="synthetic-deepseek",
            session_secret="synthetic-session-secret-1234567890",
            cors_origins=("https://beta.invalid",),
            registration_mode="invite_only",
            ai_labs_enabled=False,
            session_cookie_secure=True,
        )
        settings.validate()

    def test_production_registration_defaults_to_invite_only(self) -> None:
        with patch.dict("os.environ", {"APP_ENV": "production"}, clear=True):
            get_settings.cache_clear()
            settings = get_settings()
        get_settings.cache_clear()
        self.assertEqual(settings.registration_mode, "invite_only")

    def test_sql_binding_adapter_uses_named_parameters(self) -> None:
        sql, bindings = CompatConnection._bind("SELECT ? AS a, ? AS b", (1, "x"))
        self.assertEqual(sql, "SELECT :p0 AS a, :p1 AS b")
        self.assertEqual(bindings, {"p0": 1, "p1": "x"})

    def test_local_storage_round_trip(self) -> None:
        storage = LocalStorageProvider(self.root / "local-storage")
        key = "users/1/resume-exports/test.docx"
        storage.put(1, key, b"document")
        self.assertTrue(storage.exists(1, key))
        self.assertEqual(storage.get(1, key), b"document")

    def test_local_storage_delete_is_idempotent(self) -> None:
        storage = LocalStorageProvider(self.root / "local-storage")
        key = "users/1/resume-exports/test.pdf"
        storage.delete(1, key)
        storage.delete(1, key)
        self.assertFalse(storage.exists(1, key))

    def test_storage_rejects_cross_user_key(self) -> None:
        storage = LocalStorageProvider(self.root / "local-storage")
        with self.assertRaises(StorageError):
            storage.put(2, "users/1/resume-exports/test.pdf", b"x")

    def test_storage_rejects_directory_traversal(self) -> None:
        storage = LocalStorageProvider(self.root / "local-storage")
        with self.assertRaises(StorageError):
            storage.put(1, "users/1/resume-exports/../secret", b"x")

    def test_s3_storage_contract_and_presigned_url(self) -> None:
        client = FakeS3Client()
        settings = Settings(
            storage_backend="s3",
            s3_bucket="private",
            s3_presigned_url_seconds=120,
        )
        storage = S3StorageProvider(settings, client)
        key = "users/3/resume-exports/object.docx"
        storage.put(3, key, b"content")
        self.assertTrue(storage.exists(3, key))
        self.assertEqual(storage.get(3, key), b"content")
        self.assertIn("expires=120", storage.generate_download_url(3, key))
        storage.delete(3, key)
        self.assertFalse(storage.exists(3, key))

    def test_s3_healthcheck_uses_bucket_probe(self) -> None:
        client = FakeS3Client()
        storage = S3StorageProvider(Settings(s3_bucket="private"), client)
        self.assertTrue(storage.healthcheck())
        self.assertEqual(client.bucket_checks, 1)

    def test_registration_can_be_disabled(self) -> None:
        path = self.root / "disabled.db"
        settings = Settings(
            app_env="test",
            database_url=f"sqlite:///{path}",
            frontend_dir=PROJECT_ROOT / "frontend",
            schema_path=PROJECT_ROOT / "database" / "schema.sql",
            resume_export_dir=self.root / "disabled-exports",
            registration_mode="disabled",
        )
        with TestClient(create_app(settings, BetaMockProvider())) as client:
            response = client.post(
                "/auth/register",
                json={"username": "closed_user", "password": self.password, "display_name": "Closed"},
            )
        self.assertEqual(response.status_code, 403)

    def test_invite_registration_requires_code(self) -> None:
        client, _, _ = self.invite_client()
        response = client.post(
            "/auth/register",
            json={"username": "invite_user", "password": self.password, "display_name": "Invite"},
        )
        self.assertEqual(response.status_code, 403)

    def test_invite_registration_rejects_invalid_code(self) -> None:
        client, _, _ = self.invite_client()
        response = client.post(
            "/auth/register",
            json={"username": "invite_user", "password": self.password, "display_name": "Invite", "invite_code": "wrong"},
        )
        self.assertEqual(response.status_code, 403)

    def test_invite_registration_rejects_expired_code(self) -> None:
        client, code, _ = self.invite_client(expires_delta=timedelta(seconds=-1))
        response = client.post(
            "/auth/register",
            json={"username": "invite_user", "password": self.password, "display_name": "Invite", "invite_code": code},
        )
        self.assertEqual(response.status_code, 403)

    def test_invite_registration_rejects_disabled_code(self) -> None:
        client, code, path = self.invite_client()
        with sqlite3.connect(path) as connection:
            connection.execute("UPDATE invite_codes SET is_active = 0")
        response = client.post(
            "/auth/register",
            json={"username": "invite_user", "password": self.password, "display_name": "Invite", "invite_code": code},
        )
        self.assertEqual(response.status_code, 403)

    def test_invite_registration_success_and_limit(self) -> None:
        client, code, _ = self.invite_client(max_uses=1)
        first = client.post(
            "/auth/register",
            json={"username": "invite_one", "password": self.password, "display_name": "One", "invite_code": code},
        )
        second = client.post(
            "/auth/register",
            json={"username": "invite_two", "password": self.password, "display_name": "Two", "invite_code": code},
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 403)

    def test_duplicate_username_rolls_back_invite_use(self) -> None:
        client, code, path = self.invite_client(max_uses=2)
        payload = {"username": "same_user", "password": self.password, "display_name": "Same", "invite_code": code}
        self.assertEqual(client.post("/auth/register", json=payload).status_code, 201)
        self.assertEqual(client.post("/auth/register", json=payload).status_code, 409)
        with sqlite3.connect(path) as connection:
            used_count = connection.execute("SELECT used_count FROM invite_codes").fetchone()[0]
        self.assertEqual(used_count, 1)

    def test_plaintext_invite_is_not_stored(self) -> None:
        client, code, path = self.invite_client()
        with sqlite3.connect(path) as connection:
            stored_hash = connection.execute("SELECT code_hash FROM invite_codes").fetchone()[0]
        self.assertNotEqual(stored_hash, code)
        self.assertEqual(len(stored_hash), 64)

    def test_concurrent_invite_use_never_exceeds_limit(self) -> None:
        client, code, _ = self.invite_client(max_uses=1)
        repository = client.app.state.repository
        invite_hash = hash_invite_code(code, "invite-test-secret")
        barrier = Barrier(2)

        def create(username: str) -> str:
            salt = new_password_salt()
            barrier.wait()
            try:
                repository.create_user_with_invite(
                    username,
                    hash_password(self.password, salt),
                    salt,
                    username,
                    datetime.now(timezone.utc).isoformat(),
                    invite_hash,
                )
                return "created"
            except InviteCodeError:
                return "rejected"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(create, ("parallel_one", "parallel_two")))
        self.assertEqual(sorted(results), ["created", "rejected"])

    def test_invite_cli_defaults(self) -> None:
        args = build_parser().parse_args([])
        self.assertEqual((args.max_uses, args.expires_in_days), (1, 14))

    def test_ordinary_user_is_not_accepted_as_invite_cli_admin(self) -> None:
        self.register()
        self.assertIsNone(
            self.client.app.state.repository.find_active_admin("beta_user")
        )

    def test_export_has_configured_expiration(self) -> None:
        token = self.register()["token"]
        _, workspace = self.workspace(token)
        record = self.export(token, workspace["current_version"]["id"])
        delta = datetime.fromisoformat(record["expires_at"]) - datetime.fromisoformat(record["created_at"])
        self.assertGreaterEqual(delta, timedelta(days=6, hours=23))

    def test_expired_export_cannot_be_downloaded(self) -> None:
        token = self.register()["token"]
        _, workspace = self.workspace(token)
        record = self.export(token, workspace["current_version"]["id"])
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("UPDATE resume_exports SET expires_at = ? WHERE id = ?", ((datetime.now(timezone.utc) - timedelta(days=1)).isoformat(), record["id"]))
        response = self.client.get(
            f"/career/resume-exports/{record['id']}/download", headers=self.headers(token)
        )
        self.assertEqual(response.status_code, 410)
        detail = self.client.get(
            f"/career/resume-exports/{record['id']}", headers=self.headers(token)
        ).json()
        self.assertEqual(detail["status"], "expired")

    def test_cleanup_expired_exports_is_idempotent(self) -> None:
        token = self.register()["token"]
        _, workspace = self.workspace(token)
        record = self.export(token, workspace["current_version"]["id"])
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        with sqlite3.connect(self.database_path) as connection:
            connection.execute("UPDATE resume_exports SET expires_at = ? WHERE id = ?", (past, record["id"]))
        service = self.client.app.state.resume_export_service
        self.assertEqual(service.cleanup_expired()["deleted"], 1)
        self.assertEqual(service.cleanup_expired()["deleted"], 0)
        self.assertEqual(list(self.export_dir.glob("*")), [])

    def test_delete_application_removes_export_object(self) -> None:
        token = self.register()["token"]
        application, workspace = self.workspace(token)
        self.export(token, workspace["current_version"]["id"])
        response = self.client.delete(
            f"/career/applications/{application['id']}", headers=self.headers(token)
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(list(self.export_dir.glob("*")), [])

    def test_storage_delete_failure_preserves_application_for_retry(self) -> None:
        token = self.register()["token"]
        application, workspace = self.workspace(token)
        self.export(token, workspace["current_version"]["id"])
        storage = self.client.app.state.storage_provider
        with patch.object(storage, "delete", side_effect=RuntimeError("synthetic failure")):
            response = self.client.delete(
                f"/career/applications/{application['id']}", headers=self.headers(token)
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            self.client.get(
                f"/career/applications/{application['id']}", headers=self.headers(token)
            ).status_code,
            200,
        )

    def test_delete_resume_removes_versions_and_export(self) -> None:
        token = self.register()["token"]
        _, workspace = self.workspace(token)
        self.export(token, workspace["current_version"]["id"])
        response = self.client.delete(
            f"/career/resumes/{workspace['resume']['id']}", headers=self.headers(token)
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(list(self.export_dir.glob("*")), [])

    def test_account_delete_requires_password(self) -> None:
        token = self.register()["token"]
        response = self.client.request(
            "DELETE", "/auth/account", headers=self.headers(token, True), json={"password": "wrong-password"}
        )
        self.assertEqual(response.status_code, 403)

    def test_account_delete_removes_session_and_business_data(self) -> None:
        token = self.register()["token"]
        _, workspace = self.workspace(token)
        self.export(token, workspace["current_version"]["id"])
        response = self.client.request(
            "DELETE", "/auth/account", headers=self.headers(token, True), json={"password": self.password}
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/auth/me", headers=self.headers(token)).status_code, 401)
        self.assertEqual(list(self.export_dir.glob("*")), [])
        with sqlite3.connect(self.database_path) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)

    def test_resume_activity_does_not_store_document_preview(self) -> None:
        token = self.register()["token"]
        self.client.post(
            "/resume",
            headers=self.headers(token, True),
            json={"text": "Private resume user@example.com +8613800013800"},
        )
        with sqlite3.connect(self.database_path) as connection:
            row = connection.execute("SELECT input_preview, output_preview FROM activity_logs WHERE feature = 'resume'").fetchone()
        self.assertEqual(row, ("", ""))

    def test_activity_preview_redacts_contact_and_secret(self) -> None:
        token = self.register()["token"]
        self.client.post(
            "/translate",
            headers=self.headers(token, True),
            json={"text": "email user@example.com phone +8613800013800 token=synthetic-secret"},
        )
        with sqlite3.connect(self.database_path) as connection:
            preview = connection.execute("SELECT input_preview FROM activity_logs WHERE feature = 'translate'").fetchone()[0]
        self.assertNotIn("user@example.com", preview)
        self.assertNotIn("13800013800", preview)
        self.assertNotIn("synthetic-secret", preview)


if __name__ == "__main__":
    unittest.main()
