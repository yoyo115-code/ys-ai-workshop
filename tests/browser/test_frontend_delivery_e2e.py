import os
import unittest

try:
    from playwright.sync_api import Page, sync_playwright
except ModuleNotFoundError:  # Browser dependency is intentionally optional.
    Page = object  # type: ignore[assignment,misc]
    sync_playwright = None


BASE_URL = os.environ.get("YS_AI_E2E_BASE_URL", "http://127.0.0.1:8000")


@unittest.skipUnless(sync_playwright, "Install tests/browser/requirements.txt")
class FrontendDeliveryBrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)
        cls.page: Page = cls.browser.new_page(viewport={"width": 1440, "height": 1000})
        cls.console_errors: list[str] = []
        cls.failed_assets: list[str] = []
        cls.page.on(
            "console",
            lambda message: cls.console_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        cls.page.on(
            "response",
            lambda response: cls.failed_assets.append(
                f"{response.status} {response.url}"
            )
            if "/assets/" in response.url and response.status >= 400
            else None,
        )
        response = cls.page.goto(BASE_URL, wait_until="networkidle")
        if response is None or not response.ok:
            raise AssertionError(f"Unable to load {BASE_URL}")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.browser.close()
        cls.playwright.stop()

    def test_homepage_has_styles_and_bounded_icons(self) -> None:
        result = self.page.evaluate(
            """
            () => {
              const svgSizes = Array.from(document.querySelectorAll('svg')).map((svg) => {
                const rect = svg.getBoundingClientRect();
                return { width: rect.width, height: rect.height };
              });
              return {
                styleSheets: document.styleSheets.length,
                headerDisplay: getComputedStyle(document.querySelector('#header')).display,
                maxSvgWidth: Math.max(...svgSizes.map((item) => item.width)),
                maxSvgHeight: Math.max(...svgSizes.map((item) => item.height)),
                overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth
              };
            }
            """
        )
        self.assertGreaterEqual(result["styleSheets"], 1)
        self.assertEqual(result["headerDisplay"], "grid")
        self.assertLessEqual(result["maxSvgWidth"], 64)
        self.assertLessEqual(result["maxSvgHeight"], 64)
        self.assertFalse(result["overflow"])

    def test_login_and_registration_panel_are_operable(self) -> None:
        self.page.locator("#auth-switch-btn").click()
        self.assertTrue(self.page.locator("#display-name").is_visible())
        self.assertTrue(self.page.locator("#confirm-password").is_visible())
        self.assertEqual(self.page.locator("#login-btn").inner_text(), "创建账号")
        self.page.locator("#auth-switch-btn").click()
        self.assertFalse(self.page.locator("#display-name").is_visible())
        self.assertEqual(self.page.locator("#login-btn").inner_text(), "登录")

    def test_career_optimizer_and_ai_labs_navigation(self) -> None:
        self.assertTrue(self.page.locator("#panel-career").is_visible())
        self.page.locator('[data-tab="optimizer"]').click()
        self.assertTrue(self.page.locator("#panel-optimizer").is_visible())
        self.page.locator('[data-tab="resume"]').click()
        self.assertTrue(self.page.locator("#panel-resume").is_visible())

    def test_assets_and_console_have_no_blocking_errors(self) -> None:
        self.assertEqual(self.failed_assets, [])
        self.assertEqual(self.console_errors, [])


if __name__ == "__main__":
    unittest.main()
