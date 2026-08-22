from typing import List, Optional
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter

class LocalFixtureAdapter(BaseJobAdapter):
    """Adapter for loading mock/test job listings from local memory or files."""

    def __init__(self, fixtures: Optional[List[RawJobListing]] = None):
        super().__init__(source_name="local_fixture")
        self.fixtures = fixtures or self._default_fixtures()

    def fetch_jobs(self, query: str = "", location: str = "") -> List[RawJobListing]:
        """Returns filtered mock job listings matching query/location."""
        results = []
        q_lower = query.lower()
        loc_lower = location.lower()

        for job in self.fixtures:
            matches_q = not query or (q_lower in job.title.lower() or q_lower in job.description.lower())
            matches_loc = not location or (loc_lower in (job.location or "").lower())
            if matches_q and matches_loc:
                results.append(job)
        return results

    def _default_fixtures(self) -> List[RawJobListing]:
        return [
            RawJobListing(
                title="Senior Full Stack AI Engineer",
                company="TechCorp AI",
                location="Remote",
                description="We are seeking a Senior Full Stack AI Engineer proficient in Python, FastAPI, React, and local LLMs (Ollama) to build autonomous workflows.",
                url="https://example.com/jobs/senior-ai-engineer-101",
                source=self.source_name
            ),
            RawJobListing(
                title="Python Backend Developer",
                company="DataFlow Solutions",
                location="Hybrid - Seattle, WA",
                description="Looking for a Python Backend Developer with experience in PostgreSQL, Docker, Playwright, and building high-performance microservices.",
                url="https://example.com/jobs/python-backend-202",
                source=self.source_name
            )
        ]
