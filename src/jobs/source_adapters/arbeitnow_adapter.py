import json
import urllib.request
import urllib.parse
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class ArbeitnowJobAdapter(BaseJobAdapter):
    """Fetches high-quality tech jobs from Arbeitnow API."""

    def __init__(self):
        super().__init__(source_name="arbeitnow")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Remote", time_range: str = "3d") -> List[RawJobListing]: 
        url = "https://www.arbeitnow.com/api/job-board-api"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        results = []
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    for j in data.get("data", []):
                        t = j.get("title", "").strip()
                        c = j.get("company_name", "Company").strip()
                        l = j.get("location", location or "Remote").strip()
                        u = j.get("url", "").strip()
                        d = j.get("description", "")
                        if t and u:
                            results.append(RawJobListing(title=t, company=c, location=l, description=f"Arbeitnow Job: {t} at {c}. {d[:1000]}", url=u, source="arbeitnow"))
                            if len(results) >= 50:
                                break
        except Exception as e:
            logger.warning(f"Arbeitnow fetch notice: {e}")
        logger.info(f" Arbeitnow adapter fetched {len(results)} live jobs.")
        return results