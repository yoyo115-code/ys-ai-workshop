import sys
import secrets
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


class MockLLMProvider:
    def generate(self, prompt: str, provider: str) -> str:
        return f"mock:{provider}:{len(prompt)}"


class WorkshopApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.test_password = f"TestPassword{secrets.randbelow(100000):05d}"
        database_path = Path(self.temporary_directory.name) / "test.db"
        self.settings = Settings(
            database_url=f"sqlite:///{database_path}",
            frontend_dir=PROJECT_ROOT / "frontend",
            schema_path=PROJECT_ROOT / "database" / "schema.sql",
        )
        self.client_context = TestClient(
            create_app(self.settings, llm_provider=MockLLMProvider())
        )
        self.client = self.client_context.__enter__()

    def tearDown(self) -> None:
        self.client_context.__exit__(None, None, None)
        self.temporary_directory.cleanup()

    def register_user(self, username: str = "test_user") -> dict:
        response = self.client.post(
            "/auth/register",
            json={
                "username": username,
                "password": self.test_password,
                "display_name": "Test User",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    @staticmethod
    def auth_headers(token: str) -> dict[str, str]:
        return {"X-Session-Token": token}

    def test_health(self) -> None:
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "database": "test.db"})

    def test_frontend_and_assets_are_served(self) -> None:
        page = self.client.get("/")
        stylesheet = self.client.get("/assets/css/app.css")
        script = self.client.get("/assets/js/app.js")
        self.assertEqual(page.status_code, 200)
        self.assertIn("Y's AI Workshop", page.text)
        self.assertEqual(stylesheet.status_code, 200)
        self.assertEqual(script.status_code, 200)

    def test_user_registration(self) -> None:
        payload = self.register_user()
        self.assertTrue(payload["token"])
        self.assertEqual(payload["user"]["role"], "user")

    def test_user_login(self) -> None:
        self.register_user()
        response = self.client.post(
            "/auth/login",
            json={"username": "test_user", "password": self.test_password},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["username"], "test_user")

    def test_ai_route_requires_authentication(self) -> None:
        response = self.client.post("/resume", json={"text": "example"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "请先登录")

    def test_text_tools_use_mock_provider(self) -> None:
        token = self.register_user()["token"]
        headers = self.auth_headers(token)
        requests = (
            ("/resume", {"text": "resume text"}),
            ("/copywrite", {"scene": "launch copy"}),
            ("/translate", {"text": "hello"}),
        )
        for path, payload in requests:
            with self.subTest(path=path):
                response = self.client.post(path, headers=headers, json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["reply"].startswith("mock:deepseek:"))

    def test_regular_user_cannot_access_admin(self) -> None:
        token = self.register_user()["token"]
        response = self.client.get(
            "/admin/users", headers=self.auth_headers(token)
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "仅管理员可访问")

    def test_missing_api_key_returns_clear_error(self) -> None:
        database_path = Path(self.temporary_directory.name) / "missing-key.db"
        settings = Settings(
            database_url=f"sqlite:///{database_path}",
            frontend_dir=PROJECT_ROOT / "frontend",
            schema_path=PROJECT_ROOT / "database" / "schema.sql",
        )
        with TestClient(create_app(settings)) as client:
            registered = client.post(
                "/auth/register",
                json={
                    "username": "no_key_user",
                    "password": self.test_password,
                    "display_name": "No Key User",
                },
            ).json()
            response = client.post(
                "/resume",
                headers=self.auth_headers(registered["token"]),
                json={"text": "example"},
            )
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "未配置 DEEPSEEK_API_KEY")

    def test_invalid_csv_file(self) -> None:
        token = self.register_user()["token"]
        response = self.client.post(
            "/csv-preview",
            headers=self.auth_headers(token),
            files={"file": ("invalid.txt", b"a,b\n1,2", "text/plain")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["detail"], "请上传 CSV 文件")

    def test_invalid_pdf_file(self) -> None:
        token = self.register_user()["token"]
        response = self.client.post(
            "/pdf-summary",
            headers=self.auth_headers(token),
            files={"file": ("invalid.pdf", b"not-a-pdf", "application/pdf")},
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("PDF 解析失败", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
