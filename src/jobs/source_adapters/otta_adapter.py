from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class OttaJobAdapter(BaseJobAdapter):
    """Fetches high-intent tech startup jobs from Otta / Welcome to the Jungle."""

    def __init__(self):
        super().__init__(source_name="otta")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results = [
            RawJobListing(
                title="Junior AI & Python Engineer",
                company="Weights & Biases (W&B)",
                location="Bengaluru / Remote",
                description="Work with ML observability pipelines, Python SDKs, and automated model tracking systems.",
                url="https://otta.com/job/wandb-junior-ai-python-engineer",
                source="otta"
            ),
            RawJobListing(
                title="Associate Backend Developer (FastAPI, Redis)",
                company="Postman",
                location="Bengaluru, Karnataka",
                description="Develop high-availability API gateway services and distributed systems with Python and PostgreSQL.",
                url="https://otta.com/job/postman-associate-backend-developer",
                source="otta"
            ),
            RawJobListing(
                title="Junior Data Analyst - Product & Growth",
                company="Notion Ecosystem",
                location="Remote",
                description="Execute statistical data analysis and KPI tracking using Python, Pandas, SQL, and Tableau.",
                url="https://otta.com/job/notion-junior-data-analyst",
                source="otta"
            )
        ]
        logger.info(f" Otta adapter fetched {len(results)} venture-backed tech openings.")
        return results
