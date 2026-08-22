from abc import ABC, abstractmethod
from typing import List
from src.jobs.schemas import RawJobListing

class BaseJobAdapter(ABC):
    """Abstract base class for all job source adapters."""

    def __init__(self, source_name: str):
        self.source_name = source_name

    @abstractmethod
    def fetch_jobs(self, query: str = "", location: str = "") -> List[RawJobListing]:
        """Fetches raw job listings from the target source."""
        pass
