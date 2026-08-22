import json
import urllib.request
import urllib.parse
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class JobicyJobAdapter(BaseJobAdapter):
    """Fetches high-quality remote tech job postings from Jobicy API."""

    def __init__(self):
        super().__init__(source_name="jobicy")

    def fetch_jobs(self, query: str = "python", location: str = "remote", time_range: str = "3d") -> List[RawJobListing]:
        tag = "python" if "python" in query.lower() else "engineering"
        url = f"https://jobicy.com/api/v2/remote-jobs?count=20&tag={tag}"

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
                    jobs_data = data.get("jobs", [])

                    for item in jobs_data:
                        title = item.get("jobTitle", "").strip()
                        company = item.get("companyName", "").strip()
                        job_url = item.get("url", "").strip()
                        desc = item.get("jobDescription", "")
                        loc = item.get("jobGeo", "Remote") or "Remote"

                        if not title or not job_url:
                            continue

                        # Filter for backend/developer/python roles
                        title_lower = title.lower()
                        if any(k in title_lower for k in ["python", "backend", "developer", "engineer", "software", "api"]):
                            results.append(
                                RawJobListing(
                                    title=title,
                                    company=company or "Remote Tech Company",
                                    location=loc,
                                    description=desc[:2000] if desc else f"Remote {title} at {company}",
                                    url=job_url,
                                    source="jobicy"
                                )
                            )
        except Exception as e:
            logger.warning(f"Jobicy remote fetch notice: {e}")

        logger.info(f" Jobicy adapter fetched {len(results)} remote jobs.")
        return results
