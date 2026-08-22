import json
import urllib.request
import urllib.parse
from typing import List, Optional
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class HiristJobAdapter(BaseJobAdapter):
    """
    Adapter for scraping high-quality technology jobs from Hirist.com / Hirist.tech.
    Hirist specializes in software engineering, backend, python, and distributed systems roles across India.
    """

    def __init__(self):
        super().__init__(source_name="hirist")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results: List[RawJobListing] = []
        encoded_q = urllib.parse.quote(query or "Python Developer")
        encoded_loc = urllib.parse.quote(location or "Bengaluru")
        
        url = f"https://www.hirist.tech/api/v1/jobs/search?query={encoded_q}&location={encoded_loc}&limit=25"
        
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "application/json"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    jobs_list = data.get("jobs", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    
                    for item in jobs_list:
                        title = item.get("title", "")
                        comp = item.get("company", {}).get("name", "Top Tech Co") if isinstance(item.get("company"), dict) else item.get("companyName", "Top Tech Co")
                        loc = item.get("location", "") or location or "Bengaluru"
                        skills = item.get("skills", [])
                        skills_str = ", ".join(skills[:5]) if isinstance(skills, list) else ""
                        job_id = item.get("id") or ""
                        job_url = f"https://www.hirist.tech/j/{job_id}" if job_id else f"https://www.hirist.tech/c/{encoded_q}-jobs.html"
                        desc = item.get("description", "") or f"Hirist Tech Role: {title} at {comp}. Skills: {skills_str}"

                        if title:
                            results.append(
                                RawJobListing(
                                    title=title,
                                    company=comp,
                                    location=loc,
                                    description=f"Hirist Curated Tech: {desc[:600]}",
                                    url=job_url,
                                    source="hirist"
                                )
                            )
        except Exception as e:
            logger.debug(f"[Hirist] Notice: {e}")

        logger.info(f" [Hirist] Discovered {len(results)} curated software engineering jobs.")
        return results
