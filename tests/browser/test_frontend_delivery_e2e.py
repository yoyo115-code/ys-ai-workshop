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
                headerHeight: document.querySelector('#header').getBoundingClientRect().height,
                brandMark: (() => {
                  const mark = document.querySelector('.brand-mark');
                  const container = document.querySelector('.brand-logo');
                  const markRect = mark.getBoundingClientRect();
                  const containerRect = container.getBoundingClientRect();
                  return {
                    complete: mark.complete,
                    naturalWidth: mark.naturalWidth,
                    width: markRect.width,
                    height: markRect.height,
                    centerDeltaX: Math.abs((markRect.left + markRect.width / 2) - (containerRect.left + containerRect.width / 2)),
                    centerDeltaY: Math.abs((markRect.top + markRect.height / 2) - (containerRect.top + containerRect.height / 2))
                  };
                })(),
                maxSvgWidth: Math.max(...svgSizes.map((item) => item.width)),
                maxSvgHeight: Math.max(...svgSizes.map((item) => item.height)),
                overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth
              };
            }
            """
        )
        self.assertGreaterEqual(result["styleSheets"], 1)
        self.assertEqual(result["headerDisplay"], "grid")
        self.assertLess(result["headerHeight"], 480)
        self.assertTrue(result["brandMark"]["complete"])
        self.assertGreater(result["brandMark"]["naturalWidth"], 0)
        self.assertGreaterEqual(result["brandMark"]["width"], 44)
        self.assertLessEqual(result["brandMark"]["width"], 48)
        self.assertLessEqual(result["brandMark"]["centerDeltaX"], 1)
        self.assertLessEqual(result["brandMark"]["centerDeltaY"], 1)
        self.assertLessEqual(result["maxSvgWidth"], 64)
        self.assertLessEqual(result["maxSvgHeight"], 64)
        self.assertFalse(result["overflow"])

    def test_brand_favicon_and_mark_are_http_assets(self) -> None:
        favicon = self.page.locator('link[rel="icon"]')
        self.assertTrue(favicon.get_attribute("href").endswith("/assets/brand/favicon.svg"))
        result = self.page.evaluate(
            """
            async () => {
              const urls = [
                document.querySelector('.brand-mark').src,
                document.querySelector('link[rel="icon"]').href
              ];
              const responses = await Promise.all(urls.map((url) => fetch(url)));
              return responses.map((response) => ({
                ok: response.ok,
                type: response.headers.get('content-type')
              }));
            }
            """
        )
        self.assertTrue(all(item["ok"] for item in result))
        self.assertTrue(all(item["type"].startswith("image/svg+xml") for item in result))

    def test_brand_layout_at_supported_breakpoints(self) -> None:
        for width, height in ((390, 844), (768, 1024), (1440, 1000)):
            with self.subTest(width=width):
                self.page.set_viewport_size({"width": width, "height": height})
                result = self.page.evaluate(
                    """
                    () => {
                      const bounds = (selector) => {
                        const element = document.querySelector(selector);
                        const rect = element.getBoundingClientRect();
                        return {
                          visible: !!(rect.width && rect.height),
                          left: rect.left,
                          right: rect.right,
                          top: rect.top,
                          bottom: rect.bottom,
                          width: rect.width,
                          height: rect.height
                        };
                      };
                      const career = bounds('[data-tab="career"]');
                      const optimizer = bounds('[data-tab="optimizer"]');
                      const login = bounds('.service-status');
                      return {
                        logo: bounds('.brand-mark'),
                        brandName: bounds('.brand-text h1'),
                        beta: bounds('.beta-badge'),
                        login,
                        career,
                        optimizer,
                        navOverflow: document.querySelector('#tab-nav').scrollWidth > document.querySelector('#tab-nav').clientWidth,
                        pageOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
                        withinViewport: [login, career, optimizer].every((rect) => rect.left >= 0 && rect.right <= window.innerWidth)
                      };
                    }
                    """
                )
                self.assertTrue(result["logo"]["visible"])
                self.assertTrue(result["brandName"]["visible"])
                self.assertTrue(result["beta"]["visible"])
                self.assertTrue(result["login"]["visible"])
                self.assertTrue(result["career"]["visible"])
                self.assertTrue(result["optimizer"]["visible"])
                self.assertTrue(result["withinViewport"])
                self.assertFalse(result["pageOverflow"])
                self.assertFalse(result["navOverflow"])
                if width == 390:
                    self.assertGreaterEqual(result["logo"]["width"], 32)
                    self.assertLessEqual(result["logo"]["width"], 36)
                    self.assertLess(result["career"]["bottom"], result["optimizer"]["top"])
        self.page.set_viewport_size({"width": 1440, "height": 1000})

    def test_login_and_registration_panel_are_operable(self) -> None:
        self.page.locator("#auth-switch-btn").click()
        self.assertTrue(self.page.locator("#display-name").is_visible())
        self.assertTrue(self.page.locator("#confirm-password").is_visible())
        self.assertTrue(self.page.locator("#invite-code").is_visible())
        self.assertEqual(self.page.locator("#login-btn").inner_text(), "创建账号")
        self.page.locator("#auth-switch-btn").click()
        self.assertFalse(self.page.locator("#display-name").is_visible())
        self.assertEqual(self.page.locator("#login-btn").inner_text(), "登录")

    def test_private_beta_notice_and_data_controls_exist(self) -> None:
        self.assertTrue(self.page.locator(".beta-badge").is_visible())
        self.assertTrue(self.page.locator("#privacy-notice").is_visible())
        self.assertIn("7 天", self.page.locator("#retention-summary").inner_text())
        self.assertEqual(self.page.locator("#delete-account-btn").count(), 1)

    def test_career_optimizer_and_ai_labs_navigation(self) -> None:
        self.assertTrue(self.page.locator("#panel-career").is_visible())
        self.page.locator('[data-tab="optimizer"]').click()
        self.assertTrue(self.page.locator("#panel-optimizer").is_visible())
        self.page.locator('[data-tab="resume"]').click()
        self.assertTrue(self.page.locator("#panel-resume").is_visible())

    def test_resume_export_entry_and_template_contract(self) -> None:
        self.page.locator('[data-tab="optimizer"]').click()
        self.assertTrue(self.page.locator("#optimizer-export-btn").is_visible())
        self.assertTrue(self.page.locator("#resume-export-workspace").is_hidden())
        self.assertEqual(
            self.page.locator("#export-template-select option").all_text_contents(),
            ["Professional", "Minimal ATS"],
        )
        self.assertEqual(
            self.page.locator("#export-format-select option").all_text_contents(),
            ["DOCX", "PDF"],
        )

    def test_assets_and_console_have_no_blocking_errors(self) -> None:
        self.assertEqual(self.failed_assets, [])
        self.assertEqual(self.console_errors, [])

    def test_private_beta_layout_is_responsive(self) -> None:
        self.page.set_viewport_size({"width": 390, "height": 844})
        result = self.page.evaluate(
            """
            () => ({
              overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
              noticeDirection: getComputedStyle(document.querySelector('#privacy-notice')).flexDirection,
              headerColumns: getComputedStyle(document.querySelector('#header')).gridTemplateColumns,
              brandMark: (() => {
                const mark = document.querySelector('.brand-mark').getBoundingClientRect();
                const container = document.querySelector('.brand-logo').getBoundingClientRect();
                return {
                  width: mark.width,
                  height: mark.height,
                  centerDeltaX: Math.abs((mark.left + mark.width / 2) - (container.left + container.width / 2)),
                  centerDeltaY: Math.abs((mark.top + mark.height / 2) - (container.top + container.height / 2)),
                  withinHeader: mark.left >= document.querySelector('#header').getBoundingClientRect().left && mark.right <= document.querySelector('#header').getBoundingClientRect().right
                };
              })()
            })
            """
        )
        self.assertFalse(result["overflow"])
        self.assertEqual(result["noticeDirection"], "column")
        self.assertNotIn(" ", result["headerColumns"])
        self.assertGreaterEqual(result["brandMark"]["width"], 30)
        self.assertLessEqual(result["brandMark"]["width"], 36)
        self.assertTrue(result["brandMark"]["withinHeader"])
        self.assertLessEqual(result["brandMark"]["centerDeltaX"], 1)
        self.assertLessEqual(result["brandMark"]["centerDeltaY"], 1)
        self.page.set_viewport_size({"width": 1440, "height": 1000})


if __name__ == "__main__":
    unittest.main()
