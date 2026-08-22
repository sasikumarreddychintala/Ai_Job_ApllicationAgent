import json
import urllib.request
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class RemoteOKJobAdapter(BaseJobAdapter):
    """Fetches remote tech jobs from RemoteOK public JSON endpoint."""

    def __init__(self):
        super().__init__(source_name="remoteok")

    def fetch_jobs(self, query: str = "", location: str = "") -> List[RawJobListing]:
        url = "https://remoteok.com/api"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        results = []

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    # First element in remoteok API is metadata, actual jobs start from index 1
                    jobs = data[1:] if len(data) > 1 and isinstance(data[0], dict) and "legal" in data[0] else data

                    for item in jobs:
                        if not isinstance(item, dict):
                            continue
                        title = item.get("position", "")
                        comp = item.get("company", "Remote Company")
                        job_url = item.get("url", "")
                        desc = item.get("description", "")
                        loc_val = item.get("location", "Remote")
                        tags = item.get("tags", [])

                        # Query match on title, description, or tags
                        q_match = True
                        if query:
                            q_lower = query.lower()
                            q_match = (
                                q_lower in title.lower() or
                                q_lower in desc.lower() or
                                any(q_lower in str(t).lower() for t in tags)
                            )
                        else:
                            # If no query passed, only include developer/engineer/tech jobs
                            tech_keywords = ["developer", "engineer", "software", "backend", "frontend", "python", "full stack", "data"]
                            t_lower = title.lower()
                            q_match = any(tk in t_lower for tk in tech_keywords)

                        if not q_match:
                            continue

                        if len(results) >= 15:
                            break

                        results.append(
                            RawJobListing(
                                title=title,
                                company=comp,
                                location=loc_val or "Remote",
                                description=desc or title,
                                url=job_url,
                                source="remoteok",
                                posted_date=str(item.get("date"))
                            )
                        )
        except Exception as e:
            logger.warning(f"RemoteOK fetch notice: {e}")

        logger.info(f" RemoteOK adapter fetched {len(results)} jobs.")
        return results
