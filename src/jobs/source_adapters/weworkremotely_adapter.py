import urllib.request
import xml.etree.ElementTree as ET
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class WeWorkRemotelyJobAdapter(BaseJobAdapter):
    """Fetches high-signal remote backend and developer jobs from We Work Remotely."""

    def __init__(self):
        super().__init__(source_name="weworkremotely")

    def fetch_jobs(self, query: str = "python", location: str = "remote", time_range: str = "3d") -> List[RawJobListing]:
        urls = [
            "https://weworkremotely.com/categories/remote-back-end-programming-jobs.rss",
            "https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss"
        ]

        results: List[RawJobListing] = []

        for url in urls:
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status == 200:
                        root = ET.fromstring(resp.read().decode("utf-8", errors="ignore"))
                        items = root.findall(".//item")

                        for it in items[:15]:
                            full_title = it.find("title").text if it.find("title") is not None else ""
                            link = it.find("link").text if it.find("link") is not None else ""
                            desc = it.find("description").text if it.find("description") is not None else ""

                            # Usually "Company Name: Job Title"
                            if ":" in full_title:
                                company, title = full_title.split(":", 1)
                                company = company.strip()
                                title = title.strip()
                            else:
                                company = "Remote Tech"
                                title = full_title.strip()

                            if not title or not link:
                                continue

                            results.append(
                                RawJobListing(
                                    title=title,
                                    company=company,
                                    location="Remote",
                                    description=desc[:2000] if desc else f"Remote {title} at {company}",
                                    url=link.split("?")[0],
                                    source="weworkremotely"
                                )
                            )
            except Exception as e:
                logger.warning(f"WeWorkRemotely fetch notice for {url}: {e}")

        logger.info(f" WeWorkRemotely adapter fetched {len(results)} remote jobs.")
        return results
