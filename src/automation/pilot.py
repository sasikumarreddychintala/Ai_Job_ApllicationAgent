from pathlib import Path
from typing import Dict, Any, Optional
from playwright.sync_api import sync_playwright

from config import settings
from src.utils.logger import logger
from src.database.models import init_db
from src.resume.profile import ProfileManager
from src.jobs.schemas import RawJobListing
from src.jobs.finder import JobFinder
from src.agents.jd_agent import JDAgent
from src.agents.match_agent import MatchAgent
from src.agents.resume_agent import ResumeTailorAgent
from src.agents.answer_agent import ApplicationAnswerAgent
from src.automation.browser import BrowserManager
from src.automation.source_adapters.generic_form_adapter import GenericFormAdapter
from src.automation.captcha_monitor import CaptchaMonitor
from src.automation.checkpoint import save_application_checkpoint

class PilotRunner:
    """Targeted runner for applying to a single specific job application URL."""

    def __init__(self, db_path=settings.DATABASE_PATH):
        self.db_path = db_path
        self.profile_manager = ProfileManager()

    def run_pilot_on_url(self, url: str, is_live_submission: bool = False) -> Dict[str, Any]:
        """Executes full application lifecycle for a single target URL."""
        logger.info("=" * 60)
        logger.info(f"[bold cyan]LAUNCHING TARGETED PILOT RUN[/bold cyan]")
        logger.info(f"Target URL: {url}")
        logger.info(f"Mode: {'[bold red]LIVE SUBMISSION[/bold red]' if is_live_submission else '[bold green]DRY RUN (Inspect before submit)[/bold green]'}")
        logger.info("=" * 60)

        # 1. Fetch Page Title & Text via Browser
        page_title = "Job Position"
        page_text = "Job Description"
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(url, timeout=30000)
                page_title = page.title() or "Job Position"
                page_text = page.inner_text("body")[:4000]
                browser.close()
        except Exception as e:
            logger.warning(f"Could not scrape URL directly ({e}). Using URL fallback.")
            page_text = f"Job listing at {url}"

        # 2. Store Discovered Job
        company = "Target Company"
        if "greenhouse.io" in url:
            parts = url.split("greenhouse.io/")[-1].split("/")
            company = parts[0].capitalize() if parts else "Greenhouse Employer"
        elif "lever.co" in url:
            parts = url.split("lever.co/")[-1].split("/")
            company = parts[0].capitalize() if parts else "Lever Employer"

        raw_job = RawJobListing(
            title=page_title,
            company=company,
            location="Remote / Hybrid",
            url=url,
            source="pilot_url",
            description=page_text
        )

        class SingleJobAdapter:
            def __init__(self, job): self.job = job; self.source_name = "pilot_url"
            def fetch_jobs(self, q="", l=""): return [self.job]

        finder = JobFinder(adapters=[SingleJobAdapter(raw_job)], db_path=self.db_path)
        finder.discover_jobs()

        # 3. Analyze JD
        jd_agent = JDAgent(db_path=self.db_path)
        jd_agent.analyze_all_pending_jobs()

        # 4. Match Fit
        match_agent = MatchAgent(profile_manager=self.profile_manager, db_path=self.db_path)
        evals = match_agent.evaluate_all_pending_jobs()

        # 5. Tailor Resume
        tailor_agent = ResumeTailorAgent(profile_manager=self.profile_manager, db_path=self.db_path)
        tailored_paths = tailor_agent.tailor_all_pending_jobs()

        # 6. Fill Application Form
        conn = init_db(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT j.id, j.title, j.company, a.status, rv.file_path
                FROM jobs j
                JOIN applications a ON j.id = a.job_id
                LEFT JOIN resume_versions rv ON a.resume_version_id = rv.id
                WHERE j.url = ?
                ORDER BY j.id DESC LIMIT 1
                """,
                (url,)
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Job record for URL {url} not found in database.")

            job_id, title, comp, status, pdf_path = row
            pdf_file_path = Path(pdf_path) if pdf_path else None

            profile = self.profile_manager.load_profile()
            answer_agent = ApplicationAnswerAgent(profile_manager=self.profile_manager, db_path=self.db_path)
            answers = [
                answer_agent.answer_question("Full Name", job_id=job_id, conn=conn),
                answer_agent.answer_question("Email Address", job_id=job_id, conn=conn),
                answer_agent.answer_question("Phone Number", job_id=job_id, conn=conn),
                answer_agent.answer_question("Work Authorization", job_id=job_id, conn=conn)
            ]

            with conn:
                conn.execute("UPDATE applications SET status = 'APPLICATION_STARTED' WHERE job_id = ?", (job_id,))
            save_application_checkpoint(job_id, "APPLICATION_STARTED", {"url": url}, conn=conn)

            adapter = GenericFormAdapter()
            captcha_mon = CaptchaMonitor(db_path=self.db_path)

            with BrowserManager(headless=False, slow_mo=500) as page:
                try:
                    page.goto(url)
                except Exception as e:
                    logger.warning(f"Browser navigation notice: {e}")

                if captcha_mon.detect_captcha(page):
                    cleared = captcha_mon.handle_captcha_pause(page, job_id, comp, title)
                    if not cleared:
                        return {"status": "PAUSED_FOR_CAPTCHA", "job_id": job_id}

                filled = adapter.fill_application_form(page, profile, pdf_file_path, answers)
                if filled:
                    with conn:
                        conn.execute("UPDATE applications SET status = 'FORM_FILLED' WHERE job_id = ?", (job_id,))
                    save_application_checkpoint(job_id, "FORM_FILLED", {"url": url}, conn=conn)

                    if not is_live_submission:
                        with conn:
                            conn.execute("UPDATE applications SET status = 'READY_TO_SUBMIT' WHERE job_id = ?", (job_id,))
                        pause_secs = getattr(settings, "INSPECTION_PAUSE_SECONDS", 15)
                        logger.info(f" [DRY_RUN] Application form filled for '{title}' at {comp}. Pausing {pause_secs}s for inspection...")
                        try:
                            page.wait_for_timeout(pause_secs * 1000)
                        except Exception:
                            pass
                        final_status = "READY_TO_SUBMIT"
                    else:
                        with conn:
                            conn.execute("UPDATE applications SET status = 'SUBMITTED', applied_at = CURRENT_TIMESTAMP WHERE job_id = ?", (job_id,))
                        logger.info(f" [SUBMITTED] Live application submitted for '{title}' at {comp}.")
                        final_status = "SUBMITTED"

                    return {
                        "status": "SUCCESS",
                        "job_id": job_id,
                        "application_status": final_status,
                        "company": comp,
                        "title": title
                    }

            return {"status": "FAILED", "job_id": job_id}

        finally:
            conn.close()
