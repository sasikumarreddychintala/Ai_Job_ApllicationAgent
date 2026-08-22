import json
import sqlite3
from typing import List, Optional

from config import settings
from src.utils.logger import logger
from src.database.models import init_db
from src.resume.profile import ProfileManager
from src.ai.schemas import ParsedJDRequirements, MatchEvaluation
from src.matching.scorer import calculate_match_score

class MatchAgent:
    """Agent responsible for scoring candidate fit against analyzed job descriptions and qualifying jobs."""

    def __init__(self, profile_manager: Optional[ProfileManager] = None, db_path=settings.DATABASE_PATH):
        self.profile_manager = profile_manager or ProfileManager()
        self.db_path = db_path

    def evaluate_job(self, job_id: int, conn: Optional[sqlite3.Connection] = None) -> MatchEvaluation:
        """Evaluates match score for job_id, records breakdown in job_matches table, and updates status to QUALIFIED or SKIPPED."""
        should_close = False
        if conn is None:
            conn = init_db(self.db_path)
            should_close = True

        try:
            profile = self.profile_manager.load_profile()
            if not profile:
                raise ValueError("Candidate profile not found. Please import master resume first.")

            cursor = conn.cursor()
            cursor.execute("SELECT title, company, analyzed_requirements FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row or not row[2]:
                raise ValueError(f"Job ID {job_id} not found or missing analyzed_requirements.")

            title, company, req_json_str = row
            req_dict = json.loads(req_json_str)
            requirements = ParsedJDRequirements(**req_dict)

            logger.info(f" Evaluating match fit for Job ID {job_id}: '{title}' at {company}...")

            # Calculate match evaluation
            eval_result = calculate_match_score(profile, requirements)

            # Determine new application state
            new_status = "QUALIFIED" if eval_result.decision != "SKIP" else "SKIPPED"

            # Save evaluation in SQLite job_matches table & update application status
            breakdown_json = json.dumps(eval_result.score_breakdown.model_dump())
            with conn:
                conn.execute(
                    """
                    INSERT INTO job_matches (job_id, overall_score, decision, breakdown_json)
                    VALUES (?, ?, ?, ?)
                    """,
                    (job_id, eval_result.overall_score, eval_result.decision, breakdown_json)
                )
                conn.execute(
                    "UPDATE applications SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                    (new_status, job_id)
                )

            logger.info(
                f" Match evaluation complete for Job ID {job_id}. "
                f"Score: {eval_result.overall_score}/100 ({eval_result.decision}) -> Application Status: {new_status}"
            )

            # Trigger immediate high-priority mobile alert with tailored PDF resume for top matches ONLY (>= 80%)
            min_tg_score = getattr(settings, "TELEGRAM_MIN_SCORE", 80)
            if eval_result.overall_score >= min_tg_score and eval_result.decision != "SKIP":
                try:
                    from src.notifications.notifier import NotificationManager
                    cursor.execute("SELECT source, url FROM jobs WHERE id = ?", (job_id,))
                    src_row = cursor.fetchone()
                    src_name = src_row["source"] if src_row else "Live"
                    job_url = src_row["url"] if src_row else ""
                    NotificationManager.notify_top_match_found(
                        company=company,
                        title=title,
                        score=eval_result.overall_score,
                        source=src_name,
                        url=job_url,
                        matched_skills=eval_result.matched_skills,
                        job_id=job_id
                    )
                except Exception as ne:
                    logger.debug(f"Notification dispatch notice: {ne}")

            # Real-time Live Tracker Sync (Google Sheets & Notion) for matched jobs ONLY
            if eval_result.overall_score >= 70 and eval_result.decision != "SKIP":
                try:
                    from src.sync.tracker_sync import tracker_sync
                    tracker_sync.sync_job(job_id)
                except Exception as se:
                    logger.debug(f"Tracker sync notice: {se}")

            return eval_result

        finally:
            if should_close:
                conn.close()

    def evaluate_all_pending_jobs(self) -> List[MatchEvaluation]:
        """Evaluates match fit for all jobs currently in ANALYZED application state."""
        conn = init_db(self.db_path)
        evaluations = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT j.id FROM jobs j
                JOIN applications a ON j.id = a.job_id
                WHERE a.status = 'ANALYZED'
                """
            )
            pending_ids = [row[0] for row in cursor.fetchall()]
            logger.info(f" Found {len(pending_ids)} pending jobs in ANALYZED state.")

            for j_id in pending_ids:
                res = self.evaluate_job(j_id, conn=conn)
                evaluations.append(res)

            return evaluations
        finally:
            conn.close()
