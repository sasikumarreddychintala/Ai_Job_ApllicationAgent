import time
import sqlite3
from typing import Optional
from playwright.sync_api import Page
from config import settings
from src.utils.logger import logger
from src.database.models import init_db
from src.notifications.notifier import NotificationManager
from src.automation.checkpoint import save_application_checkpoint

CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha']",
    "iframe[src*='hcaptcha']",
    "iframe[src*='cloudflare']",
    "iframe[src*='turnstile']",
    "div.g-recaptcha",
    "div.h-captcha",
    "div#cf-challenge-stage",
    "div#turnstile-wrapper",
    "text=Verify you are human",
    "text=Access denied",
    "text=Checking your browser",
    "text=Press & Hold"
]

class CaptchaMonitor:
    """Monitors DOM for anti-bot & CAPTCHA challenges, handles checkpoint pause, user alerts, and polling resume."""

    def __init__(self, db_path=settings.DATABASE_PATH):
        self.db_path = db_path

    def detect_captcha(self, page: Page) -> bool:
        """Scans page DOM for visible CAPTCHA widgets or bot challenge banners."""
        for sel in CAPTCHA_SELECTORS:
            try:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    logger.warning(f" CAPTCHA / Bot challenge detected via selector: '{sel}'")
                    return True
            except Exception:
                continue
        return False

    def handle_captcha_pause(
        self,
        page: Page,
        job_id: int,
        company: str,
        title: str,
        max_wait_seconds: int = 120,
        poll_interval: int = 2
    ) -> bool:
        """
        Pauses automation, saves checkpoint, notifies human user,
        keeps headful browser open, and polls until challenge is cleared.
        """
        logger.info(f" Pausing workflow for Job ID {job_id} due to CAPTCHA challenge...")

        # 1. Save SQLite Checkpoint & update status to CAPTCHA_WAITING
        save_application_checkpoint(job_id, "CAPTCHA_WAITING", {
            "company": company,
            "title": title,
            "url": page.url
        }, db_path=self.db_path)
        self._update_app_status(job_id, "CAPTCHA_WAITING")

        # 2. Trigger Local User Notification
        NotificationManager.notify_human_intervention(
            company=company,
            title=title,
            reason="CAPTCHA detected"
        )

        # 3. Poll DOM until challenge clears or timeout reached
        start_time = time.time()
        while time.time() - start_time < max_wait_seconds:
            if not self.detect_captcha(page):
                logger.info(" CAPTCHA / Bot challenge cleared by user! Resuming automation...")
                save_application_checkpoint(job_id, "CAPTCHA_CLEARED", {"url": page.url}, db_path=self.db_path)
                return True

            time.sleep(poll_interval)

        # 4. Timeout reached -> set MANUAL_ACTION_REQUIRED
        logger.warning(f" CAPTCHA wait timeout ({max_wait_seconds}s) reached. Setting status to MANUAL_ACTION_REQUIRED.")
        self._update_app_status(job_id, "MANUAL_ACTION_REQUIRED")
        return False

    def _update_app_status(self, job_id: int, status: str) -> None:
        conn = init_db(self.db_path)
        try:
            with conn:
                conn.execute(
                    "UPDATE applications SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                    (status, job_id)
                )
        finally:
            conn.close()
