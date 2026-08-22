import json
import urllib.request
import urllib.parse
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class NaukriJobAdapter(BaseJobAdapter):
    """Fetches live job postings from Naukri search."""

    def __init__(self):
        super().__init__(source_name="naukri")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        encoded_q = urllib.parse.quote(query or "Python Developer")
        encoded_loc = urllib.parse.quote(location or "Bengaluru")
        url = f"https://www.naukri.com/jobapi/v3/search?noOfResults=20&urlType=search_by_keyword&searchType=adv&keyword={encoded_q}&location={encoded_loc}&pageNo=1&seoKey={encoded_q}-jobs-in-{encoded_loc}"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
                "appid": "109",
                "systemid": "109",
                "clientid": "d34b21"
            }
        )

        results: List[RawJobListing] = []

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    job_details = data.get("jobDetails", [])

                    for job in job_details:
                        title = job.get("title", "")
                        comp_name = job.get("companyName", "Company")
                        loc_list = [l.get("label", "") for l in job.get("placeholders", []) if l.get("type") == "location"]
                        loc_str = ", ".join(loc_list) or location
                        job_id = job.get("jobId", "")
                        job_url = f"https://www.naukri.com/job-listings-{job_id}" if job_id else job.get("staticUrl", "")
                        desc = job.get("jobDescription", "")

                        if title and job_url:
                            results.append(
                                RawJobListing(
                                    title=title,
                                    company=comp_name,
                                    location=loc_str,
                                    description=desc or f"{title} at {comp_name}",
                                    url=job_url,
                                    source="naukri"
                                )
                            )
        except Exception as e:
            logger.warning(f"Naukri live job fetch notice: {e}")

        logger.info(f" Naukri adapter fetched {len(results)} live jobs.")
        return results
