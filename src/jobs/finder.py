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
        greenhouse_companies: List[str] = ["anthropic", "figma", "linear", "supabase", "postman", "canonical", "fivetran", "razorpay", "cred", "airtable", "gitlab"],
        lever_companies: List[str] = ["spotify", "palantir", "affirm", "fullstory"],
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
        """Discovers, normalizes, deduplicates, and persists unique job listings concurrently across all adapters."""
        import concurrent.futures
        discovered_new: List[NormalizedJob] = []
        conn = init_db(self.db_path)

        def _fetch_from_adapter(adapter: BaseJobAdapter):
            logger.info(f" Discovering jobs using adapter: '{adapter.source_name}' (Recency: {time_range})...")
            try:
                if hasattr(adapter, "fetch_jobs"):
                    import inspect
                    sig = inspect.signature(adapter.fetch_jobs)
                    if "time_range" in sig.parameters:
                        raw = adapter.fetch_jobs(query, location, time_range=time_range)
                    else:
                        raw = adapter.fetch_jobs(query, location)
                else:
                    raw = []
                logger.info(f" Fetched {len(raw)} listings from '{adapter.source_name}'.")
                return raw
            except Exception as e:
                logger.warning(f"Adapter '{adapter.source_name}' notice: {e}")
                return []

        try:
            # Parallel scraping across all source adapters with 16 high-performance threads
            all_raw_listings = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
                futures = [executor.submit(_fetch_from_adapter, ad) for ad in self.adapters]
                for future in concurrent.futures.as_completed(futures):
                    all_raw_listings.extend(future.result())

            logger.info(f" Aggregated total of {len(all_raw_listings)} listings across all job boards. Deduplicating...")

            for raw_job in all_raw_listings:
                norm_job = normalize_job_listing(raw_job)

                # Deduplication check
                if is_job_duplicate(norm_job.fingerprint, norm_job.url, conn):
                    continue

                # Save new unique job to SQLite
                self._save_job_to_db(conn, norm_job)
                discovered_new.append(norm_job)

            logger.info(f" Job discovery complete. {len(discovered_new)} new unique jobs stored in SQLite.")
            return discovered_new
        finally:
            conn.close()

    def _save_job_to_db(self, conn: sqlite3.Connection, job: NormalizedJob) -> int:
        """Persists normalized job record and initial DISCOVERED application state into SQLite."""
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
