import hashlib
import sqlite3
from typing import Optional
from src.database.models import init_db
from src.utils.logger import logger

def generate_job_fingerprint(company: str, title: str, url: str, location: str = "") -> str:
    """
    Generates a stable, reproducible SHA-256 hash fingerprint for a job listing.
    Normalized strings are lowercased and stripped of punctuation before hashing.
    Location is included so the same role in different cities is treated as unique.
    """
    norm_company = company.lower().strip()
    norm_title = title.lower().strip()
    norm_url = url.lower().strip().split("?")[0]  # strip URL query parameters for stability
    norm_location = location.lower().strip()
    
    raw_str = f"{norm_company}|{norm_title}|{norm_url}|{norm_location}"
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

def is_job_duplicate(fingerprint: str, url: str, conn: Optional[sqlite3.Connection] = None) -> bool:
    """
    Checks if a job with the given fingerprint or URL already exists in SQLite database.
    Returns True if duplicate, False if unique/new.
    """
    should_close = False
    if conn is None:
        conn = init_db()
        should_close = True

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM jobs WHERE fingerprint = ? OR url = ?",
            (fingerprint, url)
        )
        row = cursor.fetchone()
        is_dup = row is not None
        if is_dup:
            logger.info(f" Duplicate job detected (ID: {row[0]}, Fingerprint: {fingerprint[:8]}...)")
        return is_dup
    finally:
        if should_close:
            conn.close()
