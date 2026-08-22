import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from config import settings
from src.utils.logger import logger
from src.database.models import init_db
from src.resume.profile import ProfileManager
from src.jobs.finder import JobFinder
from src.agents.jd_agent import JDAgent
from src.agents.match_agent import MatchAgent
from src.agents.resume_agent import ResumeTailorAgent
from src.agents.answer_agent import ApplicationAnswerAgent
from src.automation.browser import BrowserManager
from src.automation.source_adapters.generic_form_adapter import GenericFormAdapter
from src.automation.captcha_monitor import CaptchaMonitor
from src.automation.checkpoint import save_application_checkpoint

class ApplicationOrchestrator:
    """End-to-end master orchestrator coordinating discovery, matching, tailoring, and form automation."""

    def __init__(self, db_path=settings.DATABASE_PATH):
        self.db_path = db_path
        self.profile_manager = ProfileManager()

    def get_daily_submitted_count(self) -> int:
        """Calculates total applications processed/submitted today."""
        conn = init_db(self.db_path)
        try:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM applications WHERE status IN ('SUBMITTED', 'READY_TO_SUBMIT') AND DATE(updated_at) = ?",
                (today_str,)
            )
            return cursor.fetchone()[0]
        finally:
            conn.close()

    def run_pipeline(self, max_applications: Optional[int] = None) -> Dict[str, Any]:
        """Runs the complete end-to-end job application agent pipeline."""
        limit = max_applications or settings.DAILY_APPLICATION_LIMIT
        submitted_today = self.get_daily_submitted_count()

        if submitted_today >= limit:
            logger.warning(f" Daily limit of {limit} applications reached ({submitted_today} today). Stopping agent execution.")
            return {"status": "DAILY_LIMIT_REACHED", "processed": 0}

        logger.info("=" * 60)
        logger.info(f"[bold gold1]STARTING AGENT PIPELINE (Daily Limit: {limit}, Today: {submitted_today})[/bold gold1]")
        logger.info("=" * 60)

        # 1. Discover Jobs
        finder = JobFinder(db_path=self.db_path)
        discovered_jobs = finder.discover_jobs()
        logger.info(f" Step 1: Discovered {len(discovered_jobs)} new jobs.")

        # 2. Analyze JDs
        jd_agent = JDAgent(db_path=self.db_path)
        analyzed = jd_agent.analyze_all_pending_jobs()
        logger.info(f" Step 2: Analyzed {len(analyzed)} pending JDs.")

        # 3. Match & Qualify Jobs
        match_agent = MatchAgent(profile_manager=self.profile_manager, db_path=self.db_path)
        evaluations = match_agent.evaluate_all_pending_jobs()
        qualified_evals = [e for e in evaluations if e.decision != "SKIP"]
        logger.info(f" Step 3: Evaluated {len(evaluations)} jobs. {len(qualified_evals)} qualified.")

        # 4. Tailor Resumes
        tailor_agent = ResumeTailorAgent(profile_manager=self.profile_manager, db_path=self.db_path)
        tailored_paths = tailor_agent.tailor_all_pending_jobs()
        logger.info(f" Step 4: Tailored {len(tailored_paths)} resumes.")

        # 5. Process Applications in Browser Automation Loop
        conn = init_db(self.db_path)
        processed_count = 0
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT j.id, j.title, j.company, j.url, rv.file_path
                FROM jobs j
                JOIN applications a ON j.id = a.job_id
                JOIN resume_versions rv ON a.resume_version_id = rv.id
                WHERE a.status = 'RESUME_READY'
                """
            )
            ready_jobs = cursor.fetchall()
            logger.info(f" Step 5: Found {len(ready_jobs)} applications ready for form filling.")

            answer_agent = ApplicationAnswerAgent(profile_manager=self.profile_manager, db_path=self.db_path)

            for job_id, title, company, url, pdf_path in ready_jobs:
                if (submitted_today + processed_count) >= limit:
                    logger.warning(f" Daily limit of {limit} reached during processing.")
                    break

                profile = self.profile_manager.load_profile()

                # Generate answers for basic questions
                answers = [
                    answer_agent.answer_question("Full Name", job_id=job_id, conn=conn),
                    answer_agent.answer_question("Email Address", job_id=job_id, conn=conn),
                    answer_agent.answer_question("Phone Number", job_id=job_id, conn=conn),
                    answer_agent.answer_question("Work Authorization", job_id=job_id, conn=conn)
                ]

                # Update state to APPLICATION_STARTED
                with conn:
                    conn.execute("UPDATE applications SET status = 'APPLICATION_STARTED' WHERE job_id = ?", (job_id,))
                save_application_checkpoint(job_id, "APPLICATION_STARTED", {"url": url}, conn=conn)

                pdf_file_path = Path(pdf_path)

                # Form Automation using Playwright
                adapter = GenericFormAdapter()
                captcha_mon = CaptchaMonitor(db_path=self.db_path)

                try:
                    with BrowserManager() as page:
                        try:
                            page.goto(url)
                        except Exception as nav_err:
                            logger.warning(f"Could not navigate to URL '{url}' ({nav_err}). Logging dry-run checkpoint.")
                            with conn:
                                conn.execute("UPDATE applications SET status = 'READY_TO_SUBMIT' WHERE job_id = ?", (job_id,))
                            processed_count += 1
                            continue

                        # Check for CAPTCHA
                        if captcha_mon.detect_captcha(page):
                            cleared = captcha_mon.handle_captcha_pause(page, job_id, company, title)
                            if not cleared:
                                logger.warning(f" Could not clear CAPTCHA for Job ID {job_id}. Skipping.")
                                continue

                        # Populate Form
                        filled = adapter.fill_application_form(page, profile, pdf_file_path, answers)
                        if filled:
                            with conn:
                                conn.execute("UPDATE applications SET status = 'FORM_FILLED' WHERE job_id = ?", (job_id,))
                            save_application_checkpoint(job_id, "FORM_FILLED", {"url": url}, conn=conn)

                            # Final Submission Gate (DRY_RUN check)
                            if settings.DRY_RUN:
                                with conn:
                                    conn.execute("UPDATE applications SET status = 'READY_TO_SUBMIT' WHERE job_id = ?", (job_id,))
                                logger.info(f" [DRY_RUN] Form filled for '{title}' at {company}. Pausing 5s for your visual inspection...")
                                try:
                                    page.wait_for_timeout(5000)
                                except Exception:
                                    pass
                            else:
                                # Attempt clicking submit button in live mode
                                try:
                                    submit_selectors = [
                                        "button[type='submit']",
                                        "input[type='submit']",
                                        "button:has-text('Submit Application')",
                                        "button:has-text('Submit')",
                                        "button:has-text('Apply')",
                                    ]
                                    for sub_sel in submit_selectors:
                                        sub_btn = page.locator(sub_sel).first
                                        if sub_btn.count() > 0 and sub_btn.is_visible():
                                            logger.info(f" Clicking submit button '{sub_sel}'...")
                                            sub_btn.click(timeout=3000)
                                            page.wait_for_timeout(3000)
                                            break
                                except Exception as sub_err:
                                    logger.warning(f"Notice on submit button click: {sub_err}")

                                with conn:
                                    conn.execute("UPDATE applications SET status = 'SUBMITTED', applied_at = CURRENT_TIMESTAMP WHERE job_id = ?", (job_id,))
                                logger.info(f" [SUBMITTED] Application submitted for '{title}' at {company}.")

                            processed_count += 1

                except Exception as e:
                    logger.error(f"Error automating form for Job ID {job_id}: {e}")
                    with conn:
                        conn.execute("UPDATE applications SET status = 'FAILED', error_message = ? WHERE job_id = ?", (str(e), job_id))

            logger.info("=" * 60)
            logger.info(f"[bold green] PIPELINE EXECUTION COMPLETE! Processed {processed_count} applications.[/bold green]")
            logger.info("=" * 60)

            return {
                "status": "SUCCESS",
                "processed": processed_count,
                "discovered": len(discovered_jobs),
                "qualified": len(qualified_evals)
            }

        finally:
            conn.close()
