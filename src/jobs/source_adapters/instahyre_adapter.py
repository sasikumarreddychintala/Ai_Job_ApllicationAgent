import json
import urllib.request
import urllib.parse
from typing import List, Optional
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class InstahyreJobAdapter(BaseJobAdapter):
    """
    Adapter for scraping premium Indian tech job openings from Instahyre.
    Instahyre features high-intent tech recruiters and top scaleups in Bengaluru, Hyderabad, and Remote.
    """

    def __init__(self):
        super().__init__(source_name="instahyre")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results: List[RawJobListing] = []
        encoded_q = urllib.parse.quote(query or "Python Developer")
        encoded_loc = urllib.parse.quote(location or "Bengaluru")
        
        url = f"https://www.instahyre.com/api/v1/jobs_search?skills={encoded_q}&location={encoded_loc}&offset=0"
        
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
                    jobs_list = data.get("objects", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    
                    for item in jobs_list:
                        title = item.get("title", "")
                        comp = item.get("employer", {}).get("company_name", "Top Tech Employer") if isinstance(item.get("employer"), dict) else item.get("company_name", "Top Tech Employer")
                        loc = item.get("location", "") or location or "Bengaluru"
                        skills = item.get("skills", [])
                        skills_str = ", ".join(skills[:5]) if isinstance(skills, list) else ""
                        job_id = item.get("id") or ""
                        job_url = f"https://www.instahyre.com/job-{job_id}" if job_id else f"https://www.instahyre.com/jobs"
                        desc = item.get("description", "") or f"Instahyre Opportunity: {title} at {comp}. Skills: {skills_str}"

                        if title:
                            results.append(
                                RawJobListing(
                                    title=title,
                                    company=comp,
                                    location=loc,
                                    description=f"Instahyre Direct Match: {desc[:600]}",
                                    url=job_url,
                                    source="instahyre"
                                )
                            )
        except Exception as e:
            logger.debug(f"[Instahyre] Notice: {e}")

        logger.info(f" [Instahyre] Discovered {len(results)} high-intent tech opportunities.")
        return results
