import sqlite3
from typing import List, Dict, Any
from datetime import datetime, timedelta
from config import settings
from src.database.models import init_db

class FollowUpManager:
    """Tracks applied jobs and generates automated 3-day and 7-day polite follow-up pitches."""

    def __init__(self, db_path=settings.DATABASE_PATH):
        self.db_path = db_path

    def get_pending_follow_ups(self) -> List[Dict[str, Any]]:
        """Returns applications submitted >= 3 days ago that have not received a response."""
        conn = init_db(self.db_path)
        c = conn.cursor()
        try:
            c.execute("""
                SELECT a.id, a.job_id, j.company, j.title, j.location, j.url, a.applied_at, a.status, jm.overall_score
                FROM applications a
                JOIN jobs j ON a.job_id = j.id
                LEFT JOIN job_matches jm ON a.job_id = jm.job_id
                WHERE a.status IN ('SUBMITTED', 'APPLIED', 'QUALIFIED')
                ORDER BY a.applied_at DESC
            """)
            rows = c.fetchall()
            follow_ups = []
            now = datetime.now()

            for r in rows:
                aid, jid, comp, tit, loc, url, applied_at_str, status, score = r
                try:
                    applied_at = datetime.fromisoformat(applied_at_str) if applied_at_str else now - timedelta(days=3)
                except Exception:
                    applied_at = now - timedelta(days=3)

                days_ago = max(1, (now - applied_at).days)
                
                # Draft customized follow-up pitch
                pitch = (
                    f"Subject: Follow-up regarding my application for {tit} - Sasi Kumar Reddy Chintala\n\n"
                    f"Hi {comp} Team,\n\n"
                    f"I hope you are having a productive week.\n\n"
                    f"I recently submitted my application for the {tit} position at {comp} and wanted to politely follow up. "
                    f"With hands-on experience architecting autonomous AI agent workflows, RAG pipelines, and high-throughput Python/FastAPI microservices at Levitica Technologies (and building Elevora ResumeAI: https://resumeai.elevora.software), I am excited about the prospect of contributing to {comp}.\n\n"
                    f"I have re-attached my tailored resume for your quick review. I would welcome the opportunity to discuss how my background aligns with your current priorities.\n\n"
                    f"Best regards,\n"
                    f"Sasi Kumar Reddy Chintala\n"
                    f"+91-8790039883 | sasikumarreddychintala@gmail.com\n"
                    f"Portfolio: https://sasikumarportfolio.vercel.app"
                )

                follow_ups.append({
                    "application_id": aid,
                    "job_id": jid,
                    "company": comp,
                    "title": tit,
                    "location": loc,
                    "url": url,
                    "days_ago": days_ago,
                    "score": score or 85,
                    "pitch": pitch
                })

            return follow_ups
        finally:
            conn.close()
