import json
import urllib.request
from typing import List, Optional
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.jobs.schemas import RawJobListing
from src.utils.logger import logger

class AshbyJobAdapter(BaseJobAdapter):
    """
    Direct ATS Adapter for high-growth modern tech & AI scaleups using Ashby HQ.
    Ashby is known for having 10x lower bot applications and direct engineering hiring manager access.
    """

    TOP_COMPANIES = [
        "cursor", "elevenlabs", "replit", "perplexity", "ramp", "retool",
        "weights-and-biases", "sentry", "vanta", "dbt-labs", "duolingo",
        "linear", "brex", "notion", "monzo", "browserbase", "modal", "qdrant"
    ]

    def __init__(self, target_companies: Optional[List[str]] = None):
        super().__init__(source_name="ashby")
        self.companies = target_companies or self.TOP_COMPANIES

    def fetch_jobs(self, query: Optional[str] = None, location: Optional[str] = None, time_range: Optional[str] = None) -> List[RawJobListing]:
        discovered = []
        q_lower = query.lower() if query else "python"
        terms = [t.strip() for t in q_lower.replace(",", " ").split() if len(t.strip()) > 2]

        for company in self.companies:
            url = f"https://api.ashbyhq.com/posting-api/job-board/{company}"
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/json"
                    }
                )
                with urllib.request.urlopen(req, timeout=4) as resp:
                    if resp.status != 200:
                        continue
                    data = json.loads(resp.read().decode("utf-8"))
                    jobs_list = data.get("jobs", [])

                    for item in jobs_list:
                        title = item.get("title", "")
                        tit_lower = title.lower()

                        # Match tech roles
                        is_match = any(t in tit_lower for t in terms) or any(
                            k in tit_lower for k in ["software", "backend", "python", "engineer", "developer", "full stack", "data", "infrastructure"]
                        )
                        if not is_match:
                            continue

                        loc = item.get("location", "") or (item.get("secondaryLocations", [{}])[0].get("location", "") if item.get("secondaryLocations") else "Remote / Global")
                        if location and location.lower() not in loc.lower() and "remote" not in loc.lower() and "anywhere" not in loc.lower():
                            continue

                        job_url = item.get("jobUrl", "") or f"https://jobs.ashbyhq.com/{company}/{item.get('id')}"
                        dept = item.get("department", "Engineering")

                        desc = (
                            f"Direct Engineering Opening at {company.capitalize()} ({dept}).\n"
                            f"Role: {title}\n"
                            f"Location: {loc}\n"
                            f"Apply directly via Ashby ATS: {job_url}\n"
                            f"Ashby boards have direct hiring manager review with low application clutter."
                        )

                        job = RawJobListing(
                            title=title,
                            company=company.capitalize(),
                            location=loc,
                            description=desc,
                            url=job_url,
                            source="ashby"
                        )
                        discovered.append(job)
            except Exception as e:
                logger.debug(f"[Ashby] Failed to fetch {company}: {e}")

        logger.info(f"[Ashby Direct ATS] Discovered {len(discovered)} direct openings across top modern scaleups.")
        return discovered
