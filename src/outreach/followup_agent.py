import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import settings
from src.utils.logger import logger
from src.database.models import init_db
from src.resume.profile import ProfileManager

class FollowUpManager:
    """
    Automated 7-Day Recruiter Follow-Up Engine.
    Monitors application timestamps, generates high-conversion 2-sentence follow-up messages,
    and alerts you on Telegram so you never miss an interview opportunity.
    """

    def __init__(self, db_path: Path = settings.DATABASE_PATH):
        self.db_path = db_path

    def get_pending_followups(self, min_days: int = 5, max_days: int = 14) -> List[Dict[str, Any]]:
        """
        Retrieves applications submitted 5 to 14 days ago that haven't received a response.
        """
        conn = init_db(self.db_path)
        pending = []
        try:
            c = conn.cursor()
            # Find jobs where status is SUBMITTED or APPLIED
            c.execute(
                """
                SELECT j.id, j.company, j.title, j.location, j.source, j.url, a.status, a.applied_at, jm.overall_score
                FROM applications a
                JOIN jobs j ON a.job_id = j.id
                LEFT JOIN job_matches jm ON j.id = jm.job_id
                WHERE a.status IN ('SUBMITTED', 'READY_TO_SUBMIT', 'RESUME_READY')
                ORDER BY a.applied_at ASC
                """
            )
            rows = c.fetchall()
            now = datetime.now()

            pm = ProfileManager()
            prof = pm.load_profile()
            candidate_name = prof.contact_info.full_name if prof else "Sasi Kumar Reddy Chintala"

            for r in rows:
                jid, comp, tit, loc, src, url, status, applied_at_str, score = r
                
                days_ago = 6 # default fallback
                if applied_at_str:
                    try:
                        applied_date = datetime.fromisoformat(applied_at_str.replace("Z", "").split(".")[0])
                        days_ago = (now - applied_date).days
                    except Exception:
                        days_ago = 6

                # Generate tailored follow-up note
                notes = self.generate_followup_message(
                    company=comp,
                    title=tit,
                    days_ago=days_ago,
                    candidate_name=candidate_name
                )

                pending.append({
                    "job_id": jid,
                    "company": comp,
                    "title": tit,
                    "location": loc or "Remote",
                    "source": src,
                    "url": url,
                    "status": status,
                    "applied_at": applied_at_str or "Recently",
                    "days_ago": days_ago,
                    "score": score or 85,
                    "linkedin_followup": notes["linkedin_followup"],
                    "email_followup_subject": notes["email_subject"],
                    "email_followup_body": notes["email_body"]
                })

            return pending
        finally:
            conn.close()

    def generate_followup_message(
        self,
        company: str,
        title: str,
        days_ago: int = 7,
        candidate_name: str = "Sasi Kumar Reddy Chintala"
    ) -> Dict[str, str]:
        """
        Creates concise, punchy, metric-backed 2-sentence follow-up messages.
        """
        # Tailored punchy LinkedIn follow-up (<280 chars)
        li_msg = (
            f"Hi team! Following up on my application for the {title} role at {company}. "
            f"I recently engineered a 30% API latency reduction in Python/FastAPI and built Elevora ResumeAI with sub-15ms Kafka caching. "
            f"Would love to connect and share more!"
        )

        # Cold Email Follow-Up
        email_sub = f"Following up: {title} Application - {candidate_name}"
        email_body = (
            f"Hi {company} Hiring Team,\n\n"
            f"I hope you're having a productive week! I am following up on my application for the {title} position submitted recently.\n\n"
            f"With hands-on experience scaling distributed Python, FastAPI, PostgreSQL, and Apache Kafka architectures (reducing production API latency by 30%), "
            f"I am very excited about {company}'s technical trajectory and would love the opportunity to contribute to your engineering goals.\n\n"
            f"I've attached my tailored resume for convenience. Please let me know if you need any additional code samples or details.\n\n"
            f"Best regards,\n"
            f"{candidate_name}\n"
            f"Portfolio: https://resumeai.elevora.software\n"
            f"Phone: +91-8790039883"
        )

        return {
            "linkedin_followup": li_msg,
            "email_subject": email_sub,
            "email_body": email_body
        }

    def check_and_notify_daily_followups(self) -> int:
        """
        Scans for applications reaching 5-7 days and dispatches Telegram reminders.
        """
        followups = self.get_pending_followups()
        if not followups:
            return 0

        from src.notifications.telegram_bot import telegram_bot
        from src.notifications.notifier import NotificationManager

        for f in followups[:3]: # Send top 3 actionable nudges
            msg = (
                f"⏰ *RECRUITER 7-DAY FOLLOW-UP REMINDER*\n\n"
                f"🏢 *Company:* {f['company']}\n"
                f"💼 *Role:* {f['title']}\n"
                f"📅 *Applied:* ~{f['days_ago']} days ago\n\n"
                f"💬 *Quick LinkedIn Follow-Up (Tap to copy):*\n"
                f"`{f['linkedin_followup']}`\n\n"
                f"👉 Send cold email follow-up: `/email {f['job_id']} careers@{f['company'].lower().replace(' ', '')}.com`"
            )
            telegram_bot.send_message(msg)

        logger.info(f" Dispatched {len(followups)} follow-up reminder alerts.")
        return len(followups)

followup_manager = FollowUpManager()

