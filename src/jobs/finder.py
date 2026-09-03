import sqlite3
from typing import List, Optional
from config import settings
from src.utils.logger import logger
from src.database.models import init_db
from src.jobs.schemas import NormalizedJob
from src.jobs.normalizer import normalize_job_listing
from src.jobs.deduplicator import is_job_duplicate
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.jobs.source_adapters.local_fixture_adapter import LocalFixtureAdapter
from src.jobs.source_adapters.linkedin_adapter import LinkedInJobAdapter
from src.jobs.source_adapters.naukri_adapter import NaukriJobAdapter
from src.jobs.source_adapters.remoteok_adapter import RemoteOKJobAdapter
from src.jobs.source_adapters.greenhouse_adapter import GreenhouseJobAdapter
from src.jobs.source_adapters.lever_adapter import LeverJobAdapter
from src.jobs.source_adapters.jobicy_adapter import JobicyJobAdapter
from src.jobs.source_adapters.himalayas_adapter import HimalayasJobAdapter
from src.jobs.source_adapters.weworkremotely_adapter import WeWorkRemotelyJobAdapter
from src.jobs.source_adapters.remotive_adapter import RemotiveJobAdapter
from src.jobs.source_adapters.arbeitnow_adapter import ArbeitnowJobAdapter
from src.jobs.source_adapters.python_org_adapter import PythonOrgJobAdapter
from src.jobs.source_adapters.ashby_adapter import AshbyJobAdapter
from src.jobs.source_adapters.hn_hiring_adapter import HackerNewsHiringAdapter
from src.jobs.source_adapters.cutshort_adapter import CutshortJobAdapter
from src.jobs.source_adapters.instahyre_adapter import InstahyreJobAdapter
from src.jobs.source_adapters.hirist_adapter import HiristJobAdapter
from src.jobs.source_adapters.indeed_adapter import IndeedJobAdapter

from src.jobs.source_adapters.wellfound_adapter import WellfoundJobAdapter
from src.jobs.source_adapters.turing_adapter import TuringJobAdapter
from src.jobs.source_adapters.hirect_adapter import HirectJobAdapter
from src.jobs.source_adapters.internshala_adapter import InternshalaJobAdapter
from src.jobs.source_adapters.unstop_adapter import UnstopJobAdapter
from src.jobs.source_adapters.foundit_adapter import FounditJobAdapter
from src.jobs.source_adapters.tophire_adapter import TopHireJobAdapter
from src.jobs.source_adapters.startupjobs_adapter import StartupJobsAdapter
from src.jobs.source_adapters.yc_startup_adapter import YCStartupJobAdapter
from src.jobs.source_adapters.hasjob_adapter import HasjobAdapter
from src.jobs.source_adapters.otta_adapter import OttaJobAdapter
from src.jobs.source_adapters.dynamite_adapter import DynamiteJobsAdapter
from src.jobs.source_adapters.aijobs_adapter import AIJobsNetAdapter

# ---------------------------------------------------------------------------
# Role Synonym Expansion — ensures all equivalent job titles are searched
# ---------------------------------------------------------------------------
ROLE_SYNONYMS: dict = {
    "ai engineer": [
        "ai engineer", "ml engineer", "llm engineer", "genai engineer",
        "machine learning engineer", "applied ai engineer", "ai developer",
        "nlp engineer", "deep learning engineer", "research engineer",
    ],
    "software engineer": [
        "software engineer", "software developer", "backend engineer",
        "python developer", "backend developer", "python engineer",
        "api developer", "full stack developer", "fullstack engineer",
    ],
    "data engineer": [
        "data engineer", "etl developer", "data pipeline engineer",
        "big data engineer", "analytics engineer",
    ],
    "data scientist": [
        "data scientist", "ml researcher", "applied scientist",
        "quantitative analyst", "data analyst",
    ],
    "devops engineer": [
        "devops engineer", "cloud engineer", "platform engineer",
        "site reliability engineer", "sre", "infrastructure engineer",
    ],
}

def expand_query_terms(query: str) -> list:
    """
    Expands a single query string into all known role synonym variants.
    Returns a deduplicated list of query strings to search across all adapters.
    e.g. "ai engineer" → ["ai engineer", "ml engineer", "llm engineer", ...]
    Falls back to [query] if no synonym group matches.
    """
    q_lower = query.lower().strip()
    for canonical, synonyms in ROLE_SYNONYMS.items():
        if q_lower == canonical or q_lower in synonyms:
            return synonyms
    # Partial match: if query contains any canonical key
    for canonical, synonyms in ROLE_SYNONYMS.items():
        if canonical in q_lower or any(s in q_lower for s in synonyms):
            return synonyms
    return [query] if query else [""]


# Title-level pre-filters: block these before even saving to DB, to avoid wasted LLM calls.
_SENIOR_TITLE_KEYWORDS = [
    "senior", "sr.", " lead", "staff ", "principal", "architect",
    "director", "head of", "engineering manager", "tech lead", "vp ",
    "vice president", "chief", " cto", " ceo", "president",
]
_NON_TECH_TITLE_KEYWORDS = [
    "barber", "nanny", "driver", "lifeguard", "hostess", "janitorial",
    "cleaner", "cashier", "electrician", "handyman", "painter",
    "influencer", "sales executive", "field sales", "insurance agent",
    "nurse", "doctor", "chef", "cook", "waiter", "accountant",
    "lawyer", "legal counsel", "hr executive", "human resource",
    "content writer", "copywriter", "graphic designer", "social media manager",
    "digital marketing", "seo specialist", "brand manager", "event coordinator",
    "fashion", "beauty", "retail", "store manager", "logistics", "supply chain",
]

def _is_title_blocked(title: str) -> bool:
    """Returns True if the job title should be discarded before saving to DB."""
    t = title.lower()
    if any(k in t for k in _SENIOR_TITLE_KEYWORDS):
        return True
    if any(k in t for k in _NON_TECH_TITLE_KEYWORDS):
        return True
    return False


class JobFinder:
    """Orchestrates job discovery across 28+ adapters, deduplicates listings, and persists new jobs into SQLite."""

    def __init__(self, adapters: Optional[List[BaseJobAdapter]] = None, db_path=settings.DATABASE_PATH):
        self.adapters = adapters if adapters is not None else [
            LinkedInJobAdapter(),
            YCStartupJobAdapter(),
            HasjobAdapter(),
            OttaJobAdapter(),
            AIJobsNetAdapter(),
            DynamiteJobsAdapter(),
            UnstopJobAdapter(),
            FounditJobAdapter(),
            TopHireJobAdapter(),
            StartupJobsAdapter(),
            WellfoundJobAdapter(),
            TuringJobAdapter(),
            CutshortJobAdapter(),
            InstahyreJobAdapter(),
            HiristJobAdapter(),
            HirectJobAdapter(),
            InternshalaJobAdapter(),
            NaukriJobAdapter(),
            RemoteOKJobAdapter(),
            IndeedJobAdapter(),
            PythonOrgJobAdapter(),
            AshbyJobAdapter(),
            HackerNewsHiringAdapter(),
            RemotiveJobAdapter(),
            ArbeitnowJobAdapter(),
            JobicyJobAdapter(),
            HimalayasJobAdapter(),
            WeWorkRemotelyJobAdapter()
        ]
        self.db_path = db_path

    @classmethod
    def create_multi_source_finder(
        cls,
        greenhouse_companies: List[str] = ["anthropic", "figma", "canonical", "fivetran", "airtable", "gitlab", "stripe", "openai", "github"],
        lever_companies: List[str] = ["spotify", "palantir", "netflix", "atlassian"],
        db_path=settings.DATABASE_PATH
    ) -> "JobFinder":
        """Factory for live multi-board discovery across 28+ portals and direct ATS sources."""
        adapters: List[BaseJobAdapter] = [
            LinkedInJobAdapter(),
            YCStartupJobAdapter(),
            HasjobAdapter(),
            OttaJobAdapter(),
            AIJobsNetAdapter(),
            DynamiteJobsAdapter(),
            UnstopJobAdapter(),
            FounditJobAdapter(),
            TopHireJobAdapter(),
            StartupJobsAdapter(),
            WellfoundJobAdapter(),
            TuringJobAdapter(),
            CutshortJobAdapter(),
            InstahyreJobAdapter(),
            HiristJobAdapter(),
            HirectJobAdapter(),
            InternshalaJobAdapter(),
            NaukriJobAdapter(),
            RemoteOKJobAdapter(),
            IndeedJobAdapter(),
            PythonOrgJobAdapter(),
            AshbyJobAdapter(),
            HackerNewsHiringAdapter(),
            RemotiveJobAdapter(),
            ArbeitnowJobAdapter(),
            JobicyJobAdapter(),
            HimalayasJobAdapter(),
            WeWorkRemotelyJobAdapter()
        ]
        for gh in greenhouse_companies:
            adapters.append(GreenhouseJobAdapter(company=gh))
        for lev in lever_companies:
            adapters.append(LeverJobAdapter(company=lev))
        return cls(adapters=adapters, db_path=db_path)

    def discover_jobs(self, query: str = "", location: str = "", time_range: str = "3d") -> List[NormalizedJob]:
        """Discovers, normalizes, deduplicates, and persists unique job listings concurrently across all adapters.
        Automatically expands the query into all synonym variants (e.g. 'AI Engineer' → 10 role variants)
        to maximise relevant job discovery before deduplication.
        """
        import concurrent.futures
        discovered_new: List[NormalizedJob] = []
        conn = init_db(self.db_path)

        # Expand query into all role synonyms so adapters search all equivalent titles
        query_variants = expand_query_terms(query)
        logger.info(f" Query '{query}' expanded to {len(query_variants)} synonym variants: {query_variants}")

        def _fetch_from_adapter(adapter: BaseJobAdapter, q: str):
            logger.info(f" Discovering jobs using adapter: '{adapter.source_name}' query='{q}' (Recency: {time_range})...")
            try:
                if hasattr(adapter, "fetch_jobs"):
                    import inspect
                    sig = inspect.signature(adapter.fetch_jobs)
                    if "time_range" in sig.parameters:
                        raw = adapter.fetch_jobs(q, location, time_range=time_range)
                    else:
                        raw = adapter.fetch_jobs(q, location)
                else:
                    raw = []
                logger.info(f" Fetched {len(raw)} listings from '{adapter.source_name}' (query='{q}').")
                return raw
            except Exception as e:
                logger.warning(f"Adapter '{adapter.source_name}' notice: {e}")
                return []

        try:
            # Build all (adapter, query_variant) pairs — each adapter runs for every synonym
            fetch_tasks = [
                (adapter, q)
                for adapter in self.adapters
                for q in query_variants
            ]

            # Parallel scraping across all source adapters × all query variants
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                futures = [executor.submit(_fetch_from_adapter, ad, q) for ad, q in fetch_tasks]
                for future in concurrent.futures.as_completed(futures):
                    try:
                        raw_batch = future.result()
                        for raw_job in raw_batch:
                            norm_job = normalize_job_listing(raw_job)
                            # Deduplication check — prevents same job from synonym searches being saved twice
                            if is_job_duplicate(norm_job.fingerprint, norm_job.url, conn):
                                continue
                            job_id = self._save_job_to_db(conn, norm_job)
                            if job_id > 0:
                                discovered_new.append(norm_job)
                    except Exception as e:
                        logger.debug(f"Error processing adapter batch: {e}")

            logger.info(f" Job discovery complete. {len(discovered_new)} new unique jobs stored.")
            return discovered_new
        finally:
            conn.close()




    def _save_job_to_db(self, conn: sqlite3.Connection, job: NormalizedJob) -> int:
        """Persists normalized job record and initial DISCOVERED application state into SQLite.
        Returns 0 (skipped) or the new job DB id.
        """
        # Pre-filter: block senior/non-tech titles at discovery time
        if _is_title_blocked(job.title):
            logger.debug(f"[PRE-FILTER] Skipping title before DB save: '{job.title}'")
            return 0

        with conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO jobs (fingerprint, title, company, location, source, url, raw_jd, normalized_jd)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.fingerprint,
                    job.title,
                    job.company,
                    job.location,
                    job.source,
                    job.url,
                    job.description,
                    job.description
                )
            )
            job_db_id = cursor.lastrowid

            # Create initial application tracking entry with status 'DISCOVERED'
            cursor.execute(
                "INSERT INTO applications (job_id, status) VALUES (?, 'DISCOVERED')",
                (job_db_id,)
            )
            return job_db_id
