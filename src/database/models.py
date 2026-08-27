import sqlite3
from pathlib import Path
from config import settings
from src.utils.logger import logger

SCHEMA_SQL = """
-- Candidate Profile
CREATE TABLE IF NOT EXISTS candidate_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_text TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Discovered & Normalized Jobs
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    source TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    raw_jd TEXT NOT NULL,
    normalized_jd TEXT,
    analyzed_requirements TEXT,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Qualification & Match Evaluations
CREATE TABLE IF NOT EXISTS job_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    overall_score INTEGER NOT NULL,
    decision TEXT CHECK(decision IN ('SKIP', 'APPLY', 'HIGH', 'VERY_HIGH')) NOT NULL,
    breakdown_json TEXT NOT NULL,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

-- Resume Versions (Tailored derivative outputs)
CREATE TABLE IF NOT EXISTS resume_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    tailored_text TEXT NOT NULL,
    changes_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES jobs(id)
);

-- Applications State Machine Trackers
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    resume_version_id INTEGER,
    status TEXT CHECK(status IN (
        'DISCOVERED', 'ANALYZED', 'MATCHED', 'QUALIFIED', 'SKIPPED',
        'DUPLICATE', 'RESUME_READY', 'APPLICATION_STARTED', 'FORM_FILLED',
        'READY_TO_SUBMIT', 'SUBMITTED', 'CAPTCHA_WAITING',
        'MANUAL_ACTION_REQUIRED', 'FAILED'
    )) NOT NULL DEFAULT 'DISCOVERED',
    applied_at TIMESTAMP,
    error_message TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(job_id) REFERENCES jobs(id),
    FOREIGN KEY(resume_version_id) REFERENCES resume_versions(id)
);

-- Approved & Reusable Answers
CREATE TABLE IF NOT EXISTS application_answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_hash TEXT UNIQUE NOT NULL,
    question_text TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    source TEXT CHECK(source IN ('GENERATED', 'USER_APPROVED')) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Event Logs / Checkpoints for Auditability & Recovery
CREATE TABLE IF NOT EXISTS application_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    event_payload TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(application_id) REFERENCES applications(id)
);

-- Execution Agent Runs
CREATE TABLE IF NOT EXISTS agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    jobs_processed INTEGER DEFAULT 0,
    applications_submitted INTEGER DEFAULT 0,
    status TEXT NOT NULL
);

-- Key-Value System Settings
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

POSTGRES_SCHEMA_SQL = """
-- Candidate Profile
CREATE TABLE IF NOT EXISTS candidate_profile (
    id SERIAL PRIMARY KEY,
    raw_text TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Discovered & Normalized Jobs
CREATE TABLE IF NOT EXISTS jobs (
    id SERIAL PRIMARY KEY,
    fingerprint TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    source TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    raw_jd TEXT NOT NULL,
    normalized_jd TEXT,
    analyzed_requirements TEXT,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Qualification & Match Evaluations
CREATE TABLE IF NOT EXISTS job_matches (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    overall_score INTEGER NOT NULL,
    decision TEXT NOT NULL,
    breakdown_json TEXT NOT NULL,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Resume Versions
CREATE TABLE IF NOT EXISTS resume_versions (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    file_path TEXT NOT NULL,
    tailored_text TEXT NOT NULL,
    changes_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Applications State Machine
CREATE TABLE IF NOT EXISTS applications (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    resume_version_id INTEGER REFERENCES resume_versions(id),
    status TEXT NOT NULL DEFAULT 'DISCOVERED',
    applied_at TIMESTAMP,
    error_message TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Approved & Reusable Answers
CREATE TABLE IF NOT EXISTS application_answers (
    id SERIAL PRIMARY KEY,
    question_hash TEXT UNIQUE NOT NULL,
    question_text TEXT NOT NULL,
    answer_text TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Event Logs / Checkpoints
CREATE TABLE IF NOT EXISTS application_events (
    id SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id),
    event_type TEXT NOT NULL,
    event_payload TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Execution Agent Runs
CREATE TABLE IF NOT EXISTS agent_runs (
    id SERIAL PRIMARY KEY,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    jobs_processed INTEGER DEFAULT 0,
    applications_submitted INTEGER DEFAULT 0,
    status TEXT NOT NULL
);

-- Key-Value System Settings
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_DB_INITIALIZED = False

def init_db(db_path: Path = settings.DATABASE_PATH):
    """Initializes database connection and schema tables (SQLite or PostgreSQL)."""
    global _DB_INITIALIZED

    if getattr(settings, "DATABASE_TYPE", "sqlite") == "postgres" and getattr(settings, "DATABASE_URL", ""):
        try:
            import psycopg2
            conn = psycopg2.connect(settings.DATABASE_URL)
            with conn.cursor() as cur:
                cur.execute(POSTGRES_SCHEMA_SQL)
            conn.commit()
            if not _DB_INITIALIZED:
                logger.info("PostgreSQL database initialized successfully.")
                _DB_INITIALIZED = True
            return conn
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL database: {e}")
            logger.info("Falling back to SQLite database...")

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        with conn:
            conn.executescript(SCHEMA_SQL)
        return conn
    except Exception as e:
        logger.error(f"Failed to initialize SQLite database at {db_path}: {e}")
        raise e


if __name__ == "__main__":
    init_db()
