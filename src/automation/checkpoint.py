import json
import sqlite3
from typing import Optional, Dict, Any
from config import settings
from src.database.models import init_db
from src.utils.logger import logger

def save_application_checkpoint(
    job_id: int,
    step_name: str,
    payload: Dict[str, Any],
    conn: Optional[sqlite3.Connection] = None
) -> int:
    """Saves a step execution checkpoint into SQLite application_events table."""
    should_close = False
    if conn is None:
        conn = init_db(settings.DATABASE_PATH)
        should_close = True

    try:
        cursor = conn.cursor()
        # Find application_id for job_id
        cursor.execute("SELECT id FROM applications WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        app_id = row[0] if row else job_id

        payload_json = json.dumps(payload, ensure_ascii=False)
        with conn:
            cursor.execute(
                """
                INSERT INTO application_events (application_id, event_type, event_payload)
                VALUES (?, ?, ?)
                """,
                (app_id, step_name, payload_json)
            )
            event_id = cursor.lastrowid

        logger.info(f" Saved checkpoint '{step_name}' for Job ID {job_id} (Event ID {event_id}).")
        return event_id
    finally:
        if should_close:
            conn.close()

def load_latest_checkpoint(
    job_id: int,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[Dict[str, Any]]:
    """Loads the most recent step checkpoint payload for a job_id."""
    should_close = False
    if conn is None:
        conn = init_db(settings.DATABASE_PATH)
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM applications WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None

        app_id = row[0]
        cursor.execute(
            """
            SELECT event_type, event_payload FROM application_events
            WHERE application_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (app_id,)
        )
        evt_row = cursor.fetchone()
        if not evt_row:
            return None

        event_type, payload_str = evt_row
        payload = json.loads(payload_str)
        payload["step_name"] = event_type
        return payload
    finally:
        if should_close:
            conn.close()
