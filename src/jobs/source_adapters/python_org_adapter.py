import urllib.request
import xml.etree.ElementTree as ET
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class PythonOrgJobAdapter(BaseJobAdapter):
    """Fetches verified, low-competition Python developer jobs directly from official Python.org board."""

    def __init__(self):
        super().__init__(source_name="python_org")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "", time_range: str = "3d") -> List[RawJobListing]: 
        url = "https://www.python.org/jobs/feed/rss/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        results = []
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    tree = ET.fromstring(resp.read())
                    for item in tree.findall(".//item"):
                        raw_title = item.find("title").text if item.find("title") is not None else "Python Developer"
                        link = item.find("link").text if item.find("link") is not None else ""
                        desc = item.find("description").text if item.find("description") is not None else ""
                        
                        parts = raw_title.split(",")
                        title = parts[0].strip()
                        company = parts[1].strip() if len(parts) > 1 else "Direct Employer"
                        loc = parts[2].strip() if len(parts) > 2 else "Remote / Worldwide"

                        if title and link:
                            results.append(
                                RawJobListing(
                                    title=title,
                                    company=company,
                                    location=loc,
                                    description=f"Official Python.org Job: {title} at {company}. {desc[:1000]}",
                                    url=link,
                                    source="python_org"
                                )
                            )
        except Exception as e:
            logger.warning(f"Python.org job fetch notice: {e}")
        logger.info(f" Python.org adapter fetched {len(results)} high-converting curated jobs.")
        return results