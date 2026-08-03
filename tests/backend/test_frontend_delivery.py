import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
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
        self.icons: list[str] = []
        self.images: list[str] = []

    def handle_starttag(
        self, tag: str, attributes: list[tuple[str, str | None]]
    ) -> None:
        values = dict(attributes)
        if tag == "link" and values.get("rel") == "stylesheet" and values.get("href"):
            self.stylesheets.append(values["href"] or "")
        if tag == "link" and "icon" in (values.get("rel") or "").split() and values.get("href"):
            self.icons.append(values["href"] or "")
        if tag == "img" and values.get("src"):
            self.images.append(values["src"] or "")
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
            "/assets/brand/logo-mark.svg": "image/svg+xml",
            "/assets/brand/logo-lockup.svg": "image/svg+xml",
            "/assets/brand/favicon.svg": "image/svg+xml",
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
        self.assertEqual(self.parser.icons, ["./assets/brand/favicon.svg"])

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
        script = (FRONTEND_ROOT / "assets/js/app.js").read_text(encoding="utf-8")
        self.assertIn("API_CONFIG.isFilePreview", script)
        self.assertNotIn("服务配置暂不可用", script)

    def test_brand_svg_assets_are_safe_and_self_contained(self) -> None:
        brand_directory = FRONTEND_ROOT / "assets" / "brand"
        expected = {"logo-mark.svg", "logo-lockup.svg", "favicon.svg"}
        self.assertEqual({path.name for path in brand_directory.glob("*.svg")}, expected)
        for filename in expected:
            with self.subTest(filename=filename):
                content = (brand_directory / filename).read_text(encoding="utf-8")
                root = ET.fromstring(content)
                self.assertEqual(root.tag.rsplit("}", 1)[-1], "svg")
                self.assertIn("viewBox", root.attrib)
                self.assertNotIn("width", root.attrib)
                self.assertNotIn("height", root.attrib)
                self.assertNotIn("base64", content.lower())
                self.assertNotIn("@font-face", content.lower())
                for element in root.iter():
                    self.assertNotIn(
                        element.tag.rsplit("}", 1)[-1].lower(),
                        {"script", "foreignobject", "image"},
                    )
                    for attribute, value in element.attrib.items():
                        if attribute.rsplit("}", 1)[-1] == "href":
                            self.assertTrue(value.startswith("#"), value)
                        for resource in value.split("url(")[1:]:
                            self.assertTrue(resource.lstrip().startswith("#"), value)
        mark = ET.parse(brand_directory / "logo-mark.svg").getroot()
        favicon = ET.parse(brand_directory / "favicon.svg").getroot()
        self.assertEqual(sum(node.tag.rsplit("}", 1)[-1] == "path" for node in mark.iter()), 3)
        self.assertEqual(sum(node.tag.rsplit("}", 1)[-1] == "path" for node in favicon.iter()), 3)

    def test_brand_references_replace_the_legacy_star(self) -> None:
        self.assertEqual(self.parser.images, ["./assets/brand/logo-mark.svg"])
        self.assertIn("brand-mark", self.html)
        self.assertNotIn("M16 3L19.2 11.2L28 13.4", self.html)
        for reference in self.parser.icons + self.parser.images:
            path = FRONTEND_ROOT / urlparse(reference).path.removeprefix("./")
            self.assertTrue(path.is_file(), reference)
            response = self.client.get(urlparse(urljoin("http://testserver/", reference)).path)
            self.assertEqual(response.status_code, 200, reference)
            self.assertTrue(response.headers["content-type"].startswith("image/svg+xml"))


if __name__ == "__main__":
    unittest.main()
