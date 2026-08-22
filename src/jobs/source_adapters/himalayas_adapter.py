import json
import urllib.request
import urllib.parse
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class HimalayasJobAdapter(BaseJobAdapter):
    """Fetches verified remote tech jobs from Himalayas API."""

    def __init__(self):
        super().__init__(source_name="himalayas")

    def fetch_jobs(self, query: str = "python", location: str = "remote", time_range: str = "3d") -> List[RawJobListing]:
        url = "https://himalayas.app/jobs/api?limit=25"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

        results: List[RawJobListing] = []
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    jobs_data = data.get("jobs", []) if isinstance(data, dict) else []

                    for item in jobs_data:
                        title = item.get("title", "").strip()
                        company = item.get("companyName", "").strip()
                        slug = item.get("slug", "")
                        comp_slug = item.get("companySlug", "")
                        job_url = f"https://himalayas.app/companies/{comp_slug}/jobs/{slug}" if (slug and comp_slug) else item.get("applicationLink", "")
                        desc = item.get("description", "")
                        loc = "Remote"

                        if not title or not job_url:
                            continue

                        # Filter for developer / engineer roles
                        title_lower = title.lower()
                        if any(k in title_lower for k in ["python", "backend", "developer", "engineer", "software", "fastapi", "django"]):
                            results.append(
                                RawJobListing(
                                    title=title,
                                    company=company or "Remote Tech",
                                    location=loc,
                                    description=desc[:2000] if desc else f"Remote {title} at {company}",
                                    url=job_url,
                                    source="himalayas"
                                )
                            )
        except Exception as e:
            logger.warning(f"Himalayas remote fetch notice: {e}")

        logger.info(f" Himalayas adapter fetched {len(results)} remote jobs.")
        return results
