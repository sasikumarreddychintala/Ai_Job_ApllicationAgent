import json
import urllib.request
import urllib.parse
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class RemotiveJobAdapter(BaseJobAdapter):
    """Fetches high-quality remote software engineering jobs from Remotive API."""

    def __init__(self):
        super().__init__(source_name="remotive")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Remote", time_range: str = "3d") -> List[RawJobListing]: 
        search = urllib.parse.quote(query.split()[0] if query else "python")
        url = f"https://remotive.com/api/remote-jobs?category=software-dev&search={search}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        results = []
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    for j in data.get("jobs", []):
                        t = j.get("title", "").strip()
                        c = j.get("company_name", "Company").strip()
                        l = j.get("candidate_required_location", location or "Remote").strip()
                        u = j.get("url", "").strip()
                        d = j.get("description", "")
                        if t and u:
                            results.append(RawJobListing(title=t, company=c, location=l, description=f"Remotive Job: {t} at {c}. {d[:1000]}", url=u, source="remotive"))
        except Exception as e:
            logger.warning(f"Remotive fetch notice: {e}")
        logger.info(f" Remotive adapter fetched {len(results)} live jobs.")
        return results