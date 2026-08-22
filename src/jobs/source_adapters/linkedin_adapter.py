import re
import urllib.request
import urllib.parse
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class LinkedInJobAdapter(BaseJobAdapter):
    """Fetches real live job postings from LinkedIn public jobs search with time filters (24h, 3d, 7d)."""

    def __init__(self):
        super().__init__(source_name="linkedin")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        encoded_q = urllib.parse.quote(query or "Python Developer")
        encoded_loc = urllib.parse.quote(location or "Bengaluru")
        
        # Recency mapping
        tpr_code = "r259200" # default past 3 days (3 * 24 * 3600)
        if time_range in ["24h", "1d"]:
            tpr_code = "r86400"
        elif time_range in ["3d"]:
            tpr_code = "r259200"
        elif time_range in ["7d", "1w"]:
            tpr_code = "r604800"

        results: List[RawJobListing] = []

        # Paginate first 2 pages (0, 25)
        for page_start in [0, 25]:
            url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={encoded_q}&location={encoded_loc}&f_TPR={tpr_code}&start={page_start}"
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept-Language": "en-US,en;q=0.9"
                }
            )

            try:
                with urllib.request.urlopen(req, timeout=12) as resp:
                    if resp.status == 200:
                        html = resp.read().decode("utf-8", errors="ignore")

                        cards = html.split('<li')
                        for card in cards[1:]:
                            title_match = re.search(r'base-search-card__title[^>]*>\s*([^<]+)\s*<', card)
                            company_match = re.search(r'base-search-card__subtitle[^>]*>\s*(?:<a[^>]*>)?\s*([^<]+)\s*(?:</a>)?\s*<', card)
                            loc_match = re.search(r'job-search-card__location[^>]*>\s*([^<]+)\s*<', card)
                            url_match = re.search(r'href=\"(https://[^\"]*linkedin\.com/jobs/view/[^\"]+)\"', card)

                            if title_match and url_match:
                                title = title_match.group(1).strip()
                                company = company_match.group(1).strip() if company_match else "Company"
                                loc = loc_match.group(1).strip() if loc_match else location
                                job_url = url_match.group(1).split("?")[0]

                                results.append(
                                    RawJobListing(
                                        title=title,
                                        company=company,
                                        location=loc,
                                        description=f"Live LinkedIn Job: {title} at {company} in {loc}. Requires strong experience in {query}.",
                                        url=job_url,
                                        source="linkedin"
                                    )
                                )
            except Exception as e:
                logger.warning(f"LinkedIn fetch notice (page {page_start}): {e}")
                break

        logger.info(f" LinkedIn adapter fetched {len(results)} live jobs (Recency: {time_range}).")
        return results
