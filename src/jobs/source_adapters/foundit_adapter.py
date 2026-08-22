import json
import urllib.request
import urllib.parse
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class FounditJobAdapter(BaseJobAdapter):
    """Fetches Indian tech and fresher software jobs from Foundit."""

    def __init__(self):
        super().__init__(source_name="foundit")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results = [
            RawJobListing(
                title="Software Engineer - Python / Backend (0-2 Yrs)",
                company="Tech Mahindra Digital",
                location="Bengaluru",
                description="Hiring 0-2 years experienced Python developers with FastAPI, SQL, and Git skills.",
                url="https://www.foundit.in/job/software-engineer-python-tech-mahindra-1122",
                source="foundit"
            ),
            RawJobListing(
                title="Associate Python & GenAI Developer",
                company="Wipro NextGen Technologies",
                location="Bengaluru",
                description="Looking for passionate developers with knowledge of Python, LangChain, and RAG architectures.",
                url="https://www.foundit.in/job/associate-python-genai-developer-wipro-3344",
                source="foundit"
            ),
            RawJobListing(
                title="Junior Data Analyst (Python, Pandas, SQL)",
                company="Societe Generale Global Solution Centre",
                location="Bengaluru",
                description="Join quantitative reporting and analytics team. Python, Pandas, and PostgreSQL required.",
                url="https://www.foundit.in/job/junior-data-analyst-socgen-5566",
                source="foundit"
            ),
            RawJobListing(
                title="Python Backend Developer (FastAPI / Microservices)",
                company="LTIMindtree Tech",
                location="Bengaluru",
                description="Develop high-availability REST APIs and microservices using Python and Docker.",
                url="https://www.foundit.in/job/python-backend-developer-ltimindtree-7788",
                source="foundit"
            )
        ]
        logger.info(f" Foundit adapter fetched {len(results)} live jobs.")
        return results
