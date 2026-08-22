import csv
import json
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional

from config import settings
from src.database.models import init_db
from src.utils.logger import logger

class AuditManager:
    """Provides querying and export capabilities for application tracking, matching decisions, and lifecycle audit logs."""

    def __init__(self, db_path=settings.DATABASE_PATH):
        self.db_path = db_path

    def get_application_history(self, job_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Queries application records joined with job info, match evaluations, and tailored resume paths."""
        conn = init_db(self.db_path)
        try:
            cursor = conn.cursor()
            query = """
                SELECT
                    j.id AS job_id,
                    j.title,
                    j.company,
                    j.location,
                    j.url,
                    a.status AS application_status,
                    a.applied_at,
                    a.error_message,
                    jm.overall_score,
                    jm.decision,
                    jm.breakdown_json,
                    rv.file_path AS tailored_resume_path,
                    j.discovered_at,
                    a.updated_at
                FROM jobs j
                LEFT JOIN applications a ON j.id = a.job_id
                LEFT JOIN job_matches jm ON j.id = jm.job_id
                LEFT JOIN resume_versions rv ON a.resume_version_id = rv.id
            """
            params = []
            if job_id is not None:
                query += " WHERE j.id = ?"
                params.append(job_id)

            query += " ORDER BY j.id DESC"
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()

            results = []
            for r in rows:
                breakdown = {}
                if r[10]:
                    try:
                        breakdown = json.loads(r[10])
                    except Exception:
                        pass

                results.append({
                    "job_id": r[0],
                    "title": r[1],
                    "company": r[2],
                    "location": r[3],
                    "url": r[4],
                    "status": r[5] or "UNTRACKED",
                    "applied_at": r[6],
                    "error_message": r[7],
                    "match_score": r[8],
                    "decision": r[9],
                    "score_breakdown": breakdown,
                    "tailored_resume_path": r[11],
                    "discovered_at": r[12],
                    "updated_at": r[13]
                })
            return results
        finally:
            conn.close()

    def get_application_events(self, job_id: int) -> List[Dict[str, Any]]:
        """Retrieves chronological lifecycle events recorded for a specific job."""
        conn = init_db(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT ae.id, ae.event_type, ae.event_payload, ae.created_at
                FROM application_events ae
                JOIN applications a ON ae.application_id = a.id
                WHERE a.job_id = ?
                ORDER BY ae.id ASC
                """,
                (job_id,)
            )
            rows = cursor.fetchall()
            events = []
            for r in rows:
                payload = {}
                if r[2]:
                    try:
                        payload = json.loads(r[2])
                    except Exception:
                        pass
                events.append({
                    "event_id": r[0],
                    "event_type": r[1],
                    "payload": payload,
                    "timestamp": r[3]
                })
            return events
        finally:
            conn.close()

    def export_audit_log_to_json(self, output_path: Optional[Path] = None) -> Path:
        """Exports all application history and event logs into a structured JSON audit file."""
        out_file = output_path or (settings.LOGS_DIR / "audit_export.json")
        out_file.parent.mkdir(parents=True, exist_ok=True)

        history = self.get_application_history()
        for item in history:
            item["events"] = self.get_application_events(item["job_id"])

        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

        logger.info(f" Audit log successfully exported to JSON: {out_file}")
        return out_file

    def export_audit_log_to_csv(self, output_path: Optional[Path] = None) -> Path:
        """Exports application history into a CSV file."""
        out_file = output_path or (settings.LOGS_DIR / "audit_export.csv")
        out_file.parent.mkdir(parents=True, exist_ok=True)

        history = self.get_application_history()
        fieldnames = [
            "job_id", "title", "company", "location", "url", "status",
            "match_score", "decision", "applied_at",
            "tailored_resume_path", "discovered_at", "updated_at"
        ]

        with open(out_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in history:
                writer.writerow(row)

        logger.info(f" Audit log successfully exported to CSV: {out_file}")
        return out_file
