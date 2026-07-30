import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

from fastapi.testclient import TestClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = PROJECT_ROOT / "backend"
FRONTEND_ROOT = PROJECT_ROOT / "frontend"
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stylesheets: list[str] = []
        self.scripts: list[tuple[str, bool]] = []

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attributes)
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.stylesheets.append(values["href"] or "")
        if tag == "script" and values.get("src"):
            self.scripts.append((values["src"] or "", "defer" in values))


class NoopProvider:
    def generate(self, prompt: str, provider: str) -> str:
        raise AssertionError("Static delivery tests must not call a real model")


class FrontendDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary_directory = tempfile.TemporaryDirectory()
        database_path = Path(cls.temporary_directory.name) / "frontend-delivery.db"
        settings = Settings(
            database_url=f"sqlite:///{database_path}",
            frontend_dir=FRONTEND_ROOT,
            schema_path=PROJECT_ROOT / "database" / "schema.sql",
        )
        cls.client_context = TestClient(create_app(settings, NoopProvider()))
        cls.client = cls.client_context.__enter__()
        cls.html = (FRONTEND_ROOT / "index.html").read_text(encoding="utf-8")
        cls.parser = AssetParser()
        cls.parser.feed(cls.html)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client_context.__exit__(None, None, None)
        cls.temporary_directory.cleanup()

    def test_http_page_and_static_assets_have_correct_content_types(self) -> None:
        expected = {
            "/": "text/html",
            "/assets/css/app.css": "text/css",
            "/assets/js/config.js": "text/javascript",
            "/assets/js/app.js": "text/javascript",
        }
        for url, content_type in expected.items():
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.headers["content-type"].startswith(content_type))

    def test_referenced_assets_exist_in_frontend_directory(self) -> None:
        references = self.parser.stylesheets + [src for src, _ in self.parser.scripts]
        self.assertEqual(
            references,
            ["./assets/css/app.css", "./assets/js/config.js", "./assets/js/app.js"],
        )
        for reference in references:
            parsed = urlparse(reference)
            asset_path = FRONTEND_ROOT / parsed.path.removeprefix("./")
            self.assertTrue(asset_path.is_file(), reference)

    def test_static_references_resolve_under_http_without_404(self) -> None:
        references = self.parser.stylesheets + [src for src, _ in self.parser.scripts]
        for reference in references:
            url = urljoin("http://testserver/", reference)
            response = self.client.get(urlparse(url).path)
            self.assertEqual(response.status_code, 200, reference)

    def test_html_has_no_local_absolute_file_paths(self) -> None:
        self.assertNotIn("file://", self.html)
        self.assertNotIn("/Users/", self.html)
        self.assertNotIn('href="/assets/', self.html)
        self.assertNotIn('src="/assets/', self.html)
        self.assertIn('<link rel="icon" href="data:,">', self.html)

    def test_file_preview_is_styled_and_script_order_is_deterministic(self) -> None:
        file_url = "file:///workspace/frontend/index.html"
        references = self.parser.stylesheets + [src for src, _ in self.parser.scripts]
        resolved = [urljoin(file_url, reference) for reference in references]
        self.assertEqual(
            resolved,
            [
                "file:///workspace/frontend/assets/css/app.css",
                "file:///workspace/frontend/assets/js/config.js",
                "file:///workspace/frontend/assets/js/app.js",
            ],
        )
        self.assertEqual(
            self.parser.scripts,
            [("./assets/js/config.js", True), ("./assets/js/app.js", True)],
        )
        self.assertIn('id="file-mode-notice"', self.html)
        config = (FRONTEND_ROOT / "assets/js/config.js").read_text(encoding="utf-8")
        self.assertIn('global.location.protocol === "file:"', config)


if __name__ == "__main__":
    unittest.main()
