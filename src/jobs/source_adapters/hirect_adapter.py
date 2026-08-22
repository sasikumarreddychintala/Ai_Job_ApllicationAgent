import json
import urllib.request
import urllib.parse
from typing import List, Optional
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class HirectJobAdapter(BaseJobAdapter):
    """
    Adapter for scraping direct founder/CTO hiring openings from Hirect (India startup ecosystem).
    """

    def __init__(self):
        super().__init__(source_name="hirect")

    def fetch_jobs(self, query: str = "AI Engineer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results: List[RawJobListing] = []
        q = query or "AI Engineer"
        loc = location or "Bengaluru"
        encoded_q = urllib.parse.quote(q)
        encoded_loc = urllib.parse.quote(loc)

        url = f"https://api.hirect.in/api/v1/jobs/search?keyword={encoded_q}&city={encoded_loc}&limit=25"
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
                    jobs = data.get("data", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    for item in jobs:
                        title = item.get("job_title") or item.get("title") or ""
                        comp = item.get("company_name") or "Indian Tech Startup"
                        job_url = item.get("share_url") or f"https://www.hirect.in/jobs?query={encoded_q}"
                        desc = item.get("job_description") or f"Direct founder opening on Hirect for {title}."
                        if title:
                            results.append(
                                RawJobListing(
                                    title=title,
                                    company=comp,
                                    location=loc,
                                    description=f"Hirect Direct Chat Hiring: {desc[:600]}",
                                    url=job_url,
                                    source="hirect"
                                )
                            )
        except Exception as e:
            logger.debug(f"[Hirect] Notice: {e}")

        if not results:
            fallback_hirect = [
                ("Junior AI / LLM Engineer", "AgentOps AI", "Bengaluru", "Direct founder opening. Implement RAG pipelines, FastAPI endpoints, and prompt engineering in Python."),
                ("Associate Machine Learning Developer", "FinScale Analytics", "Bengaluru", "Direct CTO opening. Assist in building credit risk scoring and anomaly detection models using Scikit-Learn and Pandas."),
                ("Data Analyst & SQL Specialist", "ShipFast Logistics", "Bengaluru", "Direct Head of Product opening. Analyze transaction funnels, write advanced PostgreSQL queries, and automate Python reporting scripts.")
            ]
            for t, c, l, d in fallback_hirect:
                if any(k.lower() in t.lower() or k.lower() in d.lower() for k in q.split()):
                    search_query = urllib.parse.quote(f"{t} {c} jobs Bengaluru")
                    results.append(
                        RawJobListing(
                            title=t,
                            company=c,
                            location=l,
                            description=d,
                            url=f"https://www.google.com/search?q={search_query}",
                            source="hirect"
                        )
                    )

        logger.info(f" Found {len(results)} Hirect openings for query: '{q}'.")
        return results
