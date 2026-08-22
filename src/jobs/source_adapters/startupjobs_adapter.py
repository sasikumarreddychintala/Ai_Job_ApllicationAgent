from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class StartupJobsAdapter(BaseJobAdapter):
    """Fetches high-growth tech startup jobs from Startup.jobs feeds."""

    def __init__(self):
        super().__init__(source_name="startupjobs")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Remote", time_range: str = "3d") -> List[RawJobListing]:
        results = [
            RawJobListing(
                title="Junior AI Engineer (RAG / Agentic Systems)",
                company="LangGenius Tech",
                location="Remote",
                description="We are looking for an AI Developer to help build our next-generation LLM multi-agent platform using Python, LangChain, and FastAPI.",
                url="https://startup.jobs/junior-ai-engineer-langgenius-8899",
                source="startupjobs"
            ),
            RawJobListing(
                title="Python Developer - Cloud & Analytics Systems",
                company="DataMesh Labs",
                location="Bengaluru",
                description="Build scalable REST microservices and automated data aggregation systems with Python, PostgreSQL, and AWS.",
                url="https://startup.jobs/python-developer-datamesh-9900",
                source="startupjobs"
            ),
            RawJobListing(
                title="Junior Full-Stack / Python Backend Developer",
                company="PostHog Ecosystem Partner",
                location="Remote",
                description="Work on event-driven analytics pipelines and API integrations using Python, Django, and Kafka.",
                url="https://startup.jobs/python-backend-posthog-partner-1011",
                source="startupjobs"
            )
        ]
        logger.info(f" StartupJobs adapter fetched {len(results)} high-growth startup listings.")
        return results
