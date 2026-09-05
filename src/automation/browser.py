from pathlib import Path
from typing import Optional
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page

from config import settings
from src.utils.logger import logger

class BrowserManager:
    """Manages Playwright browser lifecycle, persistent contexts, and diagnostic screenshots."""

    def __init__(
        self,
        headless: bool = settings.HEADLESS,
        slow_mo: int = settings.SLOW_MO,
        user_data_dir: Optional[Path] = None
    ):
        self.headless = headless
        self.slow_mo = slow_mo
        self.user_data_dir = user_data_dir or (settings.LOGS_DIR / "browser_context")
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    def start(self) -> Page:
        """Launches Playwright Chromium browser and returns active Page."""
        if self._page:
            return self._page

        # Reset active thread event loop to prevent Playwright Sync inside asyncio conflict
        import asyncio
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass

        logger.info(f" Launching Playwright Chromium with Stealth Evasion (headless={self.headless}, slow_mo={self.slow_mo}ms)...")
        self._playwright = sync_playwright().start()

        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

        if self.user_data_dir:
            self.user_data_dir.mkdir(parents=True, exist_ok=True)
            self._context = self._playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.user_data_dir),
                headless=self.headless,
                slow_mo=self.slow_mo,
                user_agent=user_agent,
                viewport={"width": 1280, "height": 800},
                locale="en-US",
                timezone_id="Asia/Kolkata",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox"
                ]
            )
            self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        else:
            self._browser = self._playwright.chromium.launch(
                headless=self.headless,
                slow_mo=self.slow_mo,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox"
                ]
            )
            self._context = self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=user_agent,
                locale="en-US",
                timezone_id="Asia/Kolkata"
            )
            self._page = self._context.new_page()

        # Comprehensive Stealth Init Scripts: Mask automation fingerprints from Cloudflare / DataDome / Kasada
        self._page.add_init_script("""
            // 1. Mask navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

            // 2. Mock chrome runtime object
            window.chrome = {
                runtime: {},
                app: { isInstalled: false },
                csi: function() {},
                loadTimes: function() {}
            };

            // 3. Mock languages and plugins
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en', 'en-IN'] });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' }
                ]
            });

            // 4. WebGL Vendor / Renderer Spoofing (masks headless SwiftShader / llvmpipe)
            try {
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) return 'Google Inc. (NVIDIA)';
                    if (parameter === 37446) return 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3070 Direct3D11 vs_5_0 ps_5_0)';
                    return getParameter.apply(this, [parameter]);
                };
            } catch (e) {}

            // 5. Mock permissions query
            try {
                const origQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        origQuery(parameters)
                );
            } catch (e) {}
        """)

        self._page.set_default_timeout(settings.BROWSER_TIMEOUT)
        logger.info(" Advanced Stealth browser context initialized successfully.")
        return self._page

    def take_screenshot(self, name: str = "failure_screenshot.png") -> Path:
        """Captures diagnostic screenshot and saves to data/logs/."""
        path = settings.LOGS_DIR / name
        if self._page:
            try:
                self._page.screenshot(path=str(path), full_page=True)
                logger.info(f" Diagnostic screenshot saved to: {path}")
            except Exception as e:
                logger.error(f"Failed to capture screenshot: {e}")
        return path

    def stop(self) -> None:
        """Closes browser context and Playwright instance cleanly."""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
            logger.info(" Playwright browser closed cleanly.")
        except Exception as e:
            logger.warning(f"Browser shutdown notice: {e}")
        finally:
            self._playwright = None
            self._browser = None
            self._context = None
            self._page = None

    def __enter__(self):
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
