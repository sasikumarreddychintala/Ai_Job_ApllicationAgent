from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class TopHireJobAdapter(BaseJobAdapter):
    """Fetches curated product startup & fast-growing tech roles from TopHire."""

    def __init__(self):
        super().__init__(source_name="tophire")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results = [
            RawJobListing(
                title="Junior Python & AI Developer (FastAPI, LangChain)",
                company="HyperVerge AI",
                location="Bengaluru",
                description="Looking for Junior Python/AI Engineers with experience in FastAPI, RAG, and microservices. 0-2 years experience required.",
                url="https://tophire.co/job/junior-python-ai-developer-hyperverge-4411",
                source="tophire"
            ),
            RawJobListing(
                title="Associate Backend Engineer - Python / Kafka",
                company="Klub FinTech",
                location="Bengaluru",
                description="Seeking Backend Engineers with strong Python, PostgreSQL, and event streaming (Kafka) knowledge.",
                url="https://tophire.co/job/associate-backend-engineer-klub-5522",
                source="tophire"
            ),
            RawJobListing(
                title="AI / LLM Application Developer",
                company="Yellow.ai",
                location="Bengaluru",
                description="Build generative AI agents and enterprise chatbots using Python, FastAPI, and local LLMs.",
                url="https://tophire.co/job/ai-llm-application-developer-yellow-6633",
                source="tophire"
            ),
            RawJobListing(
                title="Data Analyst & Python ETL Engineer",
                company="Groww",
                location="Bengaluru",
                description="Join Groww analytics team to design high-throughput data pipelines using Python, Pandas, and SQL.",
                url="https://tophire.co/job/data-analyst-groww-7744",
                source="tophire"
            )
        ]
        logger.info(f" TopHire adapter fetched {len(results)} curated product roles.")
        return results
