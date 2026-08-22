import json
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from config import settings
from src.utils.logger import logger
from src.database.models import init_db

class TrackerSyncManager:
    """
    Automated real-time job application synchronization with Google Sheets & Notion.
    Allows tracking company, role, match score, application date, job URL, and interview status.
    """

    def __init__(
        self,
        sheets_webhook: str = getattr(settings, "GOOGLE_SHEETS_WEBHOOK_URL", ""),
        notion_api_key: str = getattr(settings, "NOTION_API_KEY", ""),
        notion_database_id: str = getattr(settings, "NOTION_DATABASE_ID", ""),
        db_path: Path = settings.DATABASE_PATH
    ):
        self.sheets_webhook = sheets_webhook
        self.notion_api_key = notion_api_key
        self.notion_database_id = notion_database_id
        self.db_path = db_path

    @property
    def is_sheets_configured(self) -> bool:
        return bool(self.sheets_webhook and "http" in self.sheets_webhook)

    @property
    def is_notion_configured(self) -> bool:
        return bool(self.notion_api_key and self.notion_database_id)

    @property
    def is_configured(self) -> bool:
        return self.is_sheets_configured or self.is_notion_configured

    def sync_to_google_sheets(self, job_data: Dict[str, Any]) -> bool:
        """Appends/updates row in Google Sheets via Google Apps Script Webhook."""
        if not self.is_sheets_configured:
            return False

        try:
            payload = json.dumps(job_data).encode("utf-8")
            req = urllib.request.Request(
                self.sheets_webhook,
                data=payload,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 302):
                    logger.info(f" [Google Sheets] Synced '{job_data.get('company')}' - '{job_data.get('title')}' successfully.")
                    return True
        except Exception as e:
            logger.debug(f"[Google Sheets] Sync notice: {e}")

        return False

    def sync_to_notion(self, job_data: Dict[str, Any]) -> bool:
        """Creates a Kanban card in Notion Database."""
        if not self.is_notion_configured:
            return False

        url = "https://api.notion.com/v1/pages"
        headers = {
            "Authorization": f"Bearer {self.notion_api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }

        # Notion property mapping
        body = {
            "parent": {"database_id": self.notion_database_id},
            "properties": {
                "Company": {
                    "title": [{"text": {"content": job_data.get("company", "Company")}}]
                },
                "Role": {
                    "rich_text": [{"text": {"content": job_data.get("title", "Role")}}]
                },
                "Match Score": {
                    "number": job_data.get("score", 0)
                },
                "Status": {
                    "select": {"name": job_data.get("status", "Discovered")}
                },
                "Source": {
                    "select": {"name": job_data.get("source", "Other")}
                },
                "Job URL": {
                    "url": job_data.get("url") or None
                }
            }
        }

        try:
            data = json.dumps(body).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    logger.info(f" [Notion] Card created for '{job_data.get('company')}' successfully.")
                    return True
        except Exception as e:
            logger.debug(f"[Notion] Sync notice: {e}")

        return False

    def sync_job(self, job_id: int) -> Dict[str, Any]:
        """Fetches full job & application details from SQLite and pushes to configured targets."""
        conn = init_db(self.db_path)
        try:
            c = conn.cursor()
            c.execute(
                """
                SELECT j.id, j.company, j.title, j.location, j.source, j.url, a.status, a.applied_at, jm.overall_score, jm.decision
                FROM jobs j
                LEFT JOIN applications a ON j.id = a.job_id
                LEFT JOIN job_matches jm ON j.id = jm.job_id
                WHERE j.id = ?
                """,
                (job_id,)
            )
            row = c.fetchone()
            if not row:
                return {"success": False, "error": f"Job #{job_id} not found"}

            jid, comp, tit, loc, src, url, status, applied_at, score, dec = row
            # Strictly filter: Only store jobs that have a passing match score
            if score is None or int(score) < 70 or dec == "SKIP" or status == "SKIPPED":
                return {"success": False, "skipped": True, "reason": "Job does not have a qualified match score (>=70)."}

            job_payload = {
                "job_id": jid,
                "company": comp,
                "title": tit,
                "location": loc or "Remote",
                "source": src,
                "url": url,
                "status": status or "QUALIFIED",
                "applied_at": applied_at or datetime.now().strftime("%Y-%m-%d %H:%M"),
                "score": score or 0,
                "decision": dec or "STRONG_MATCH"
            }

            sheets_ok = self.sync_to_google_sheets(job_payload)
            notion_ok = self.sync_to_notion(job_payload)

            return {
                "success": True,
                "google_sheets": sheets_ok,
                "notion": notion_ok,
                "job": job_payload
            }
        finally:
            conn.close()

    def sync_all_qualified(self, min_score: int = 70) -> Dict[str, Any]:
        """Batch syncs strictly passing match score jobs (>=70) to Google Sheets & Notion."""
        conn = init_db(self.db_path)
        count = 0
        try:
            c = conn.cursor()
            c.execute(
                """
                SELECT j.id, j.company, j.title, j.location, j.source, j.url, a.status, a.applied_at, jm.overall_score, jm.decision
                FROM jobs j
                JOIN applications a ON j.id = a.job_id
                JOIN job_matches jm ON j.id = jm.job_id
                WHERE jm.overall_score >= ? AND jm.decision != 'SKIP' AND a.status != 'SKIPPED'
                ORDER BY jm.overall_score DESC, j.id DESC
                """,
                (min_score,)
            )
            rows = c.fetchall()
            for r in rows:
                jid, comp, tit, loc, src, url, status, applied_at, score, dec = r
                job_payload = {
                    "job_id": jid,
                    "company": comp,
                    "title": tit,
                    "location": loc or "Remote",
                    "source": src,
                    "url": url,
                    "status": status or "QUALIFIED",
                    "applied_at": applied_at or datetime.now().strftime("%Y-%m-%d"),
                    "score": score or 0,
                    "decision": dec or "STRONG_MATCH"
                }
                self.sync_to_google_sheets(job_payload)
                self.sync_to_notion(job_payload)
                count += 1

            return {
                "success": True,
                "synced_count": count,
                "message": f"Successfully synchronized {count} qualified jobs to your live tracker!"
            }
        finally:
            conn.close()

tracker_sync = TrackerSyncManager()

