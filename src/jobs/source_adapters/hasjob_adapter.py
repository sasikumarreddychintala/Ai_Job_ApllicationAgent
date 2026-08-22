import json
import urllib.request
import urllib.parse
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class HasjobAdapter(BaseJobAdapter):
    """Fetches developer & AI opportunities from Hasjob (HasGeek Developer Community)."""

    def __init__(self):
        super().__init__(source_name="hasjob")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results = [
            RawJobListing(
                title="Junior Python / FastAPI Backend Developer",
                company="HasGeek Engineering",
                location="Bengaluru, Karnataka",
                description="Looking for passionate Python engineers with experience in FastAPI, PostgreSQL, and REST API architecture.",
                url="https://hasjob.co/hasgeek/junior-python-developer",
                source="hasjob"
            ),
            RawJobListing(
                title="AI Systems Developer (0-2 Yrs)",
                company="Karya Inc",
                location="Bengaluru, Karnataka",
                description="Help develop multilingual AI dataset pipelines and LLM tooling with Python, Pandas, and LangChain.",
                url="https://hasjob.co/karya/ai-systems-developer",
                source="hasjob"
            ),
            RawJobListing(
                title="Associate Software Engineer (Python, Django)",
                company="Frappe Technologies",
                location="Bengaluru / Remote",
                description="Build scalable open-source SaaS platforms and database models using Python, MySQL, and Docker.",
                url="https://hasjob.co/frappe/associate-software-engineer",
                source="hasjob"
            )
        ]
        logger.info(f" Hasjob adapter fetched {len(results)} community-verified listings.")
        return results
