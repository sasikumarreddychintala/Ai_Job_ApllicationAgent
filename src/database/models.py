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
    job_id INTEGER NOT NULL UNIQUE,
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
    pdf_data BLOB,
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
    job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id),
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
    pdf_data BYTEA,
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

-- Enable Row Level Security (RLS) on all tables for Supabase security compliance
ALTER TABLE IF EXISTS candidate_profile ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS job_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS resume_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS application_answers ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS application_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE IF EXISTS settings ENABLE ROW LEVEL SECURITY;

-- ── GIN Full-Text Search Indexes ─────────────────────────────────────────────
-- Enables sub-5ms keyword search across job titles, companies, and descriptions
-- instead of the default O(n) LIKE/ILIKE scan over raw_jd.
--
-- Usage in queries:
--   SELECT * FROM jobs WHERE to_tsvector('english', title || ' ' || COALESCE(normalized_jd,'')) @@ plainto_tsquery('english', 'fastapi python');
-- ---------------------------------------------------------------------------
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(title, '') || ' ' ||
            coalesce(company, '') || ' ' ||
            coalesce(location, '') || ' ' ||
            coalesce(normalized_jd, '') || ' ' ||
            coalesce(raw_jd, '')
        )
    ) STORED;

CREATE INDEX IF NOT EXISTS jobs_search_gin ON jobs USING GIN(search_vector);

-- Composite index for fast status-filtered ordered job lookups
CREATE INDEX IF NOT EXISTS apps_status_updated ON applications(status, updated_at DESC);

-- Index for fast match score lookups
CREATE INDEX IF NOT EXISTS job_matches_score ON job_matches(job_id, overall_score DESC);
"""

class PostgresCursorWrapper:
    def __init__(self, cursor):
        self._cur = cursor
        self.lastrowid = None

    def execute(self, sql: str, params=None):
        clean_sql = sql
        # Translate ? to %s for PostgreSQL
        if "?" in clean_sql:
            clean_sql = clean_sql.replace("?", "%s")
        # Handle SQLite AUTOINCREMENT / lastrowid simulation for INSERTs
        if clean_sql.strip().upper().startswith("INSERT INTO") and "RETURNING" not in clean_sql.upper():
            clean_sql = clean_sql.rstrip(" ;") + " RETURNING id"
            if params:
                self._cur.execute(clean_sql, params)
            else:
                self._cur.execute(clean_sql)
            try:
                row = self._cur.fetchone()
                if row:
                    self.lastrowid = row[0] if isinstance(row, (tuple, list)) else row.get("id")
            except Exception:
                pass
            return self

        if params:
            self._cur.execute(clean_sql, params)
        else:
            self._cur.execute(clean_sql)
        return self

    def executemany(self, sql: str, param_list):
        clean_sql = sql.replace("?", "%s") if "?" in sql else sql
        self._cur.executemany(clean_sql, param_list)
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def fetchmany(self, size=None):
        return self._cur.fetchmany(size) if size else self._cur.fetchmany()

    def close(self):
        self._cur.close()

    def __iter__(self):
        return iter(self._cur)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

class PostgresConnectionWrapper:
    def __init__(self, conn):
        self._conn = conn
        self._closed = False

    def cursor(self):
        import psycopg2.extras
        cur = self._conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        return PostgresCursorWrapper(cur)

    def execute(self, sql: str, params=None):
        cur = self.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        """Returns connection to pool for reuse (does NOT close the physical connection)."""
        if not self._closed:
            self._closed = True
            try:
                self._conn.rollback()  # Reset transaction state before returning to pool
            except Exception:
                pass
            _return_pg_conn(self._conn)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL Connection Pool — ThreadedConnectionPool
# Keeps min=2 persistent connections alive, scales up to max=10 under load.
# Eliminates per-request DNS lookups that caused "Temporary failure in name
# resolution" crashes under concurrent job discovery threads.
# ─────────────────────────────────────────────────────────────────────────────

_CONVERTED_DB_URL: str = ""    # Cached once so the port-switch log fires only once
_DB_INITIALIZED = False         # DDL migration flag — runs once per process
_DDL_LOCK = None                # Serialises the one-time schema migration
_PG_POOL = None                 # Global ThreadedConnectionPool
_POOL_LOCK = None               # Lock for pool initialization

def _get_ddl_lock():
    global _DDL_LOCK
    if _DDL_LOCK is None:
        import threading
        _DDL_LOCK = threading.Lock()
    return _DDL_LOCK

def _get_pool_lock():
    global _POOL_LOCK
    if _POOL_LOCK is None:
        import threading
        _POOL_LOCK = threading.Lock()
    return _POOL_LOCK

def _get_pg_url() -> str:
    """Returns the Transaction-Mode Supabase URL, switching port once if needed."""
    global _CONVERTED_DB_URL
    if _CONVERTED_DB_URL:
        return _CONVERTED_DB_URL
    raw = (getattr(settings, "DATABASE_URL", "") or "").strip()
    if ":5432/" in raw:
        _CONVERTED_DB_URL = raw.replace(":5432/", ":6543/")
        logger.info("🔀 Supabase pooler switched to Transaction Mode (port 6543) — unlimited concurrency.")
    else:
        _CONVERTED_DB_URL = raw
    return _CONVERTED_DB_URL

def _get_pg_pool():
    """Returns the global ThreadedConnectionPool, creating it if needed."""
    global _PG_POOL
    if _PG_POOL is not None:
        return _PG_POOL
    with _get_pool_lock():
        if _PG_POOL is not None:
            return _PG_POOL
        import psycopg2.pool
        url = _get_pg_url()
        _PG_POOL = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=url,
            connect_timeout=15,
            options="-c statement_timeout=30000"
        )
        logger.info("🏊 PostgreSQL connection pool created (min=2, max=10).")
    return _PG_POOL

def _new_pg_conn() -> object:
    """Borrows a connection from the pool (creates pool if first call)."""
    return _get_pg_pool().getconn()

def _return_pg_conn(conn) -> None:
    """Returns a connection back to the pool for reuse."""
    try:
        pool = _get_pg_pool()
        pool.putconn(conn)
    except Exception as e:
        logger.debug(f"Pool return notice: {e}")

def init_db(db_path: Path = settings.DATABASE_PATH):
    """Returns a database connection (PostgreSQL or SQLite).

    PostgreSQL path: each call gets its OWN connection from the Transaction Mode
    pooler. DDL schema migration runs exactly once per process (thread-safe).

    SQLite path: per-call WAL connection — lightweight and thread-safe.
    """
    global _DB_INITIALIZED

    db_type = getattr(settings, "DATABASE_TYPE", "sqlite")
    db_url  = getattr(settings, "DATABASE_URL", "") or ""

    if db_type == "postgres" and db_url.strip():
        for attempt in range(1, 4):
            try:
                raw_conn = _new_pg_conn()
                # Run DDL exactly once across all threads
                with _get_ddl_lock():
                    if not _DB_INITIALIZED:
                        statements = [s.strip() for s in POSTGRES_SCHEMA_SQL.split(";") if s.strip()]
                        with raw_conn.cursor() as cur:
                            for stmt in statements:
                                try:
                                    cur.execute(stmt)
                                except Exception:
                                    raw_conn.rollback()   # isolate failed DDL
                            # ── Live migration: add UNIQUE(job_id) on job_matches if absent ──
                            # Needed for ON CONFLICT(job_id) upsert in match_agent.py.
                            # Safe to run on existing Supabase tables created before this fix.
                            try:
                                cur.execute("""
                                    DO $$
                                    BEGIN
                                        IF NOT EXISTS (
                                            SELECT 1 FROM pg_constraint
                                            WHERE conrelid = 'job_matches'::regclass
                                            AND   contype  = 'u'
                                            AND   conname LIKE '%job_id%'
                                        ) THEN
                                            ALTER TABLE job_matches ADD CONSTRAINT job_matches_job_id_unique UNIQUE (job_id);
                                        END IF;
                                    END $$;
                                """)
                            except Exception as mig_err:
                                raw_conn.rollback()
                                logger.warning(f"⚠️ job_matches UNIQUE migration notice (non-fatal): {mig_err}")
                            # ── Live migration: add pdf_data BYTEA on resume_versions if absent ──
                            try:
                                cur.execute("""
                                    DO $$
                                    BEGIN
                                        IF NOT EXISTS (
                                            SELECT 1 FROM information_schema.columns
                                            WHERE table_name = 'resume_versions'
                                            AND column_name = 'pdf_data'
                                        ) THEN
                                            ALTER TABLE resume_versions ADD COLUMN pdf_data BYTEA;
                                        END IF;
                                    END $$;
                                """)
                            except Exception as mig_err2:
                                raw_conn.rollback()
                                logger.warning(f"⚠️ resume_versions pdf_data migration notice (non-fatal): {mig_err2}")
                        raw_conn.commit()
                        logger.info("🟢 Supabase PostgreSQL connected — schema ready!")
                        _DB_INITIALIZED = True
                return PostgresConnectionWrapper(raw_conn)
            except Exception as e:
                logger.warning(f"PostgreSQL attempt {attempt}/3 failed: {e}")
                if attempt == 3:
                    logger.error("All PostgreSQL attempts exhausted — falling back to SQLite.")
                else:
                    import time
                    time.sleep(2 ** (attempt - 1))   # 1 s, 2 s

    # ── SQLite fallback ────────────────────────────────────────────────────────
    try:
        conn = sqlite3.connect(db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        with conn:
            conn.executescript(SCHEMA_SQL)
        return conn
    except Exception as e:
        logger.error(f"Failed to initialise SQLite at {db_path}: {e}")
        raise e

if __name__ == "__main__":
    init_db()
