import json
import urllib.request
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class LeverJobAdapter(BaseJobAdapter):
    """Fetches job postings from company Lever ATS public API."""

    def __init__(self, company: str = "spotify"):
        super().__init__(source_name="lever")
        self.company = company

    def fetch_jobs(self, query: str = "", location: str = "") -> List[RawJobListing]:
        url = f"https://api.lever.co/v0/postings/{self.company}?mode=json"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        results = []

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    jobs_data = json.loads(resp.read().decode("utf-8"))

                    for item in jobs_data:
                        title = item.get("text", "")
                        categories = item.get("categories", {})
                        loc_name = categories.get("location", "Remote")
                        job_url = item.get("hostedUrl", "")
                        desc_plain = item.get("descriptionPlain", "")

                        # Filter by query & location
                        if query and query.lower() not in title.lower() and query.lower() not in desc_plain.lower():
                            continue
                        if location and location.lower() not in loc_name.lower():
                            continue

                        results.append(
                            RawJobListing(
                                title=title,
                                company=self.company.capitalize(),
                                location=loc_name,
                                description=desc_plain or title,
                                url=job_url,
                                source="lever",
                                posted_date=str(item.get("createdAt"))
                            )
                        )
        except Exception as e:
            logger.debug(f"Lever fetch notice for '{self.company}': {e}")

        logger.info(f" Lever adapter fetched {len(results)} jobs for '{self.company}'.")
        return results
