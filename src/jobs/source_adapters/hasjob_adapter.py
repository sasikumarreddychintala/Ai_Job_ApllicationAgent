import json
import urllib.request
import urllib.parse
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class HasjobAdapter(BaseJobAdapter):
    """Fetches live developer & AI opportunities from Hasjob (HasGeek Developer Community) via their public API."""

    BASE_URL = "https://hasjob.co/api/1/jobs"

    def __init__(self):
        super().__init__(source_name="hasjob")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results = []
        try:
            params = urllib.parse.urlencode({
                "q": query or "Python",
                "l": location or "Bengaluru",
                "c": "tech",   # category: tech jobs only
            })
            url = f"{self.BASE_URL}?{params}"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; JobAgent/1.0)",
                    "Accept": "application/json"
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            jobs = data if isinstance(data, list) else data.get("jobs", [])
            for job in jobs[:20]:
                job_url = job.get("url", "") or job.get("apply_url", "")
                if not job_url or not job_url.startswith("http"):
                    continue
                results.append(RawJobListing(
                    title=job.get("title", ""),
                    company=job.get("company", ""),
                    location=job.get("location") or location,
                    description=job.get("description", "") or job.get("blurb", ""),
                    url=job_url,
                    source="hasjob"
                ))
            logger.info(f" Hasjob adapter fetched {len(results)} live listings.")
        except Exception as e:
            logger.warning(f"Hasjob adapter notice: {e}")
        return results
