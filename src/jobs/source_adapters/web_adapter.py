import urllib.request
import re
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class WebJobAdapter(BaseJobAdapter):
    """Generic web scraper adapter for fetching job listings via HTTP/HTML."""

    def __init__(self, target_urls: List[str]):
        super().__init__(source_name="web_generic")
        self.target_urls = target_urls

    def fetch_jobs(self, query: str = "", location: str = "") -> List[RawJobListing]:
        listings = []
        for url in self.target_urls:
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as response:
                    html = response.read().decode("utf-8", errors="ignore")
                    title = self._extract_title(html)
                    company = self._extract_company(html)
                    description = self._clean_html(html)

                    listing = RawJobListing(
                        title=title,
                        company=company,
                        location=location or "Remote",
                        description=description,
                        url=url,
                        source=self.source_name
                    )
                    listings.append(listing)
            except Exception as e:
                logger.warning(f"Failed to fetch web job from {url}: {e}")
        return listings

    def _extract_title(self, html: str) -> str:
        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE)
        return match.group(1).strip() if match else "Unknown Job Title"

    def _extract_company(self, html: str) -> str:
        return "Target Company"

    def _clean_html(self, html: str) -> str:
        text = re.sub(r"<script.*?>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<style.*?>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"<.*?>", " ", text)
        return re.sub(r"\s+", " ", text).strip()
