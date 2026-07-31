import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


class PostgreSQLMockProvider:
    def generate(self, prompt: str, provider: str) -> str:
        if "SECURITY AND EVIDENCE RULES" in prompt:
            return json.dumps(
                {
                    "overall_alignment": "partial_alignment",
                    "covered_requirements": [],
                    "partially_covered_requirements": [],
                    "missing_requirements": [],
                    "uncertain_requirements": [],
                    "resume_expression_issues": [],
                    "qualification_risks": [],
                    "summary": "Synthetic PostgreSQL integration result.",
                    "analysis_limitations": ["Synthetic test only."],
                }
            )
        return "synthetic"


@unittest.skipUnless(os.getenv("TEST_POSTGRES_URL"), "PostgreSQL service not available")
class PostgreSQLIntegrationTests(unittest.TestCase):
    def test_auth_and_career_repository_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(
                app_env="test",
                database_url=os.environ["TEST_POSTGRES_URL"],
                frontend_dir=PROJECT_ROOT / "frontend",
                schema_path=PROJECT_ROOT / "database" / "schema.sql",
                resume_export_dir=Path(directory),
            )
            with TestClient(create_app(settings, PostgreSQLMockProvider())) as client:
                username = "postgres_beta_user"
                register = client.post(
                    "/auth/register",
                    json={"username": username, "password": "PostgresTest123", "display_name": "Postgres Beta"},
                )
                self.assertEqual(register.status_code, 201, register.text)
                token = register.json()["token"]
                created = client.post(
                    "/career/applications",
                    headers={"X-Session-Token": token},
                    data={"resume_text": "Built Python APIs.", "job_description": "Requires Python APIs.", "language": "en"},
                )
                self.assertEqual(created.status_code, 201, created.text)
                listed = client.get(
                    "/career/applications", headers={"X-Session-Token": token}
                )
                self.assertEqual(listed.status_code, 200)
                self.assertEqual(len(listed.json()), 1)
                analyzed = client.post(
                    f"/career/applications/{created.json()['id']}/analyze",
                    headers={"X-Session-Token": token},
                )
                self.assertEqual(analyzed.status_code, 200, analyzed.text)
                usage = client.get(
                    "/usage/daily", headers={"X-Session-Token": token}
                )
                self.assertEqual(usage.status_code, 200)
                self.assertEqual(
                    usage.json()["quotas"]["career_analysis"]["used"], 1
                )


if __name__ == "__main__":
    unittest.main()
