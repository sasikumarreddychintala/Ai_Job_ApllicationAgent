import json
import urllib.request
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class GreenhouseJobAdapter(BaseJobAdapter):
    """Fetches job postings from company Greenhouse ATS public API."""

    def __init__(self, company: str = "github"):
        super().__init__(source_name="greenhouse")
        self.company = company

    def fetch_jobs(self, query: str = "", location: str = "") -> List[RawJobListing]:
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.company}/jobs?content=true"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        results = []

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    jobs_data = data.get("jobs", [])

                    for item in jobs_data:
                        title = item.get("title", "")
                        loc_name = item.get("location", {}).get("name", "Remote")
                        job_url = item.get("absolute_url", "")
                        content = item.get("content", "")

                        # Filter by query & location
                        if query and query.lower() not in title.lower() and query.lower() not in content.lower():
                            continue
                        if location and location.lower() not in loc_name.lower():
                            continue

                        results.append(
                            RawJobListing(
                                title=title,
                                company=self.company.capitalize(),
                                location=loc_name,
                                description=content or title,
                                url=job_url,
                                source="greenhouse",
                                posted_date=item.get("updated_at")
                            )
                        )
        except Exception as e:
            logger.debug(f"Greenhouse fetch notice for '{self.company}': {e}")

        logger.info(f" Greenhouse adapter fetched {len(results)} jobs for '{self.company}'.")
        return results
