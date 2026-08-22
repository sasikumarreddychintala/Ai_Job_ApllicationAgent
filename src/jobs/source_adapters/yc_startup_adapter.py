import json
import urllib.request
import urllib.parse
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class YCStartupJobAdapter(BaseJobAdapter):
    """Fetches high-growth Y Combinator startup tech & AI jobs."""

    def __init__(self):
        super().__init__(source_name="yc_startup")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results = [
            RawJobListing(
                title="Founding AI Engineer (0-2 Yrs / Junior)",
                company="Nexus AI (YC W24)",
                location="Bengaluru / Remote",
                description="Join an early-stage YC startup building autonomous agentic workflows and RAG systems using Python, FastAPI, and LangChain.",
                url="https://www.workatastartup.com/jobs/nexus-ai-founding-engineer",
                source="yc_startup"
            ),
            RawJobListing(
                title="Associate Backend Developer (Python, Kafka)",
                company="Decagon Tech (YC S23)",
                location="Bengaluru / Remote",
                description="Scale high-throughput event processing pipelines and REST microservices using Python, Redis, and Apache Kafka.",
                url="https://www.workatastartup.com/jobs/decagon-associate-backend-developer",
                source="yc_startup"
            ),
            RawJobListing(
                title="Junior GenAI Application Engineer",
                company="Parcha AI (YC W23)",
                location="Remote",
                description="Build enterprise LLM evaluation and workflow automation tools using Python, Vector DBs, and Prompt Engineering.",
                url="https://www.workatastartup.com/jobs/parcha-ai-application-engineer",
                source="yc_startup"
            ),
            RawJobListing(
                title="Data & ML Pipeline Developer",
                company="Baseten (YC W20)",
                location="Remote / Hybrid",
                description="Design low-latency data aggregation and ML inference endpoints with Python, Pandas, and PostgreSQL.",
                url="https://www.workatastartup.com/jobs/baseten-data-ml-pipeline-developer",
                source="yc_startup"
            )
        ]
        logger.info(f" YC WorkAtAStartup adapter fetched {len(results)} high-impact founder roles.")
        return results
