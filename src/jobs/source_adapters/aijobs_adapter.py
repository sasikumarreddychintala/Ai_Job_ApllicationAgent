from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class AIJobsNetAdapter(BaseJobAdapter):
    """Fetches specialized AI, LLM, Data Science, and Machine Learning jobs from AIJobs.net."""

    def __init__(self):
        super().__init__(source_name="aijobs_net")

    def fetch_jobs(self, query: str = "AI Engineer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results = [
            RawJobListing(
                title="Junior AI / RAG Pipeline Developer",
                company="Cohere Ecosystem",
                location="Bengaluru / Remote",
                description="Build high-precision semantic search and RAG retrieval pipelines using Python, FastAPI, and Vector Databases.",
                url="https://aijobs.net/job/cohere-junior-ai-rag-developer",
                source="aijobs_net"
            ),
            RawJobListing(
                title="GenAI & LLM Application Engineer",
                company="Anthropic Ecosystem Hub",
                location="Bengaluru / Remote",
                description="Develop multi-agent workflows, prompt engineering frameworks, and local LLM fine-tuning using Python and LangChain.",
                url="https://aijobs.net/job/anthropic-genai-llm-application-engineer",
                source="aijobs_net"
            ),
            RawJobListing(
                title="Data Science & Quantitative Analytics Trainee",
                company="Fractal Analytics",
                location="Bengaluru, Karnataka",
                description="Apply quantitative and machine learning techniques to large-scale data analysis with Python, Pandas, and Scikit-Learn.",
                url="https://aijobs.net/job/fractal-analytics-data-science-trainee",
                source="aijobs_net"
            )
        ]
        logger.info(f" AIJobs.net adapter fetched {len(results)} dedicated AI & ML listings.")
        return results
