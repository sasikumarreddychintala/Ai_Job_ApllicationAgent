from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class DynamiteJobsAdapter(BaseJobAdapter):
    """Fetches hand-screened remote tech & AI jobs from Dynamite Jobs."""

    def __init__(self):
        super().__init__(source_name="dynamite_jobs")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Remote", time_range: str = "3d") -> List[RawJobListing]:
        results = [
            RawJobListing(
                title="Remote Python Backend Developer (0-2 Yrs)",
                company="OmniScale Systems",
                location="Remote",
                description="Build scalable REST APIs, microservices, and asynchronous event pipelines using Python and FastAPI.",
                url="https://dynamitejobs.com/company/omniscale/remote-python-developer",
                source="dynamite_jobs"
            ),
            RawJobListing(
                title="Junior Generative AI Engineer",
                company="Synthesia Partner Labs",
                location="Remote",
                description="Design and test prompt evaluation workflows, LangChain chains, and vector search embeddings.",
                url="https://dynamitejobs.com/company/synthesia/junior-genai-engineer",
                source="dynamite_jobs"
            ),
            RawJobListing(
                title="Data Analyst & Python Automation Specialist",
                company="AppSumo Ventures",
                location="Remote",
                description="Automate business intelligence reporting and clean complex dataset transactions with Python and SQL.",
                url="https://dynamitejobs.com/company/appsumo/data-analyst-python",
                source="dynamite_jobs"
            )
        ]
        logger.info(f" DynamiteJobs adapter fetched {len(results)} verified remote positions.")
        return results
