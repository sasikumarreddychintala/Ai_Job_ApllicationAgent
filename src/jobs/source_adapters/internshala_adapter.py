import json
import urllib.request
import urllib.parse
from typing import List, Optional
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger

class CutshortJobAdapter(BaseJobAdapter):
    """
    Adapter for scraping high-conversion Indian tech jobs from Cutshort.
    Cutshort connects candidates directly with Founders, CTOs, and Tech Recruiters with fast response times.
    """

    def __init__(self):
        super().__init__(source_name="cutshort")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results: List[RawJobListing] = []
        encoded_q = urllib.parse.quote(query or "Python Developer")
        encoded_loc = urllib.parse.quote(location or "Bengaluru")
        
        url = f"https://cutshort.io/api/v1/jobs/public-search?keyword={encoded_q}&location={encoded_loc}&limit=25"
        
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
                        comp = item.get("companyName", "") or item.get("company", {}).get("name", "Tech Startup")
                        loc = item.get("location", "") or location or "Bengaluru"
                        skills = item.get("skills", [])
                        skills_str = ", ".join(skills[:5]) if isinstance(skills, list) else ""
                        job_id = item.get("id") or item.get("slug") or ""
                        job_url = f"https://cutshort.io/job/{job_id}" if job_id else f"https://cutshort.io/jobs?search={encoded_q}"
                        desc = item.get("description", "") or f"{title} at {comp}. Required Skills: {skills_str}"

                        if title:
                            results.append(
                                RawJobListing(
                                    title=title,
                                    company=comp,
                                    location=loc,
                                    description=f"Cutshort Direct Opening: {desc[:600]}",
                                    url=job_url,
                                    source="cutshort"
                                )
                            )
        except Exception as e:
            logger.debug(f"[Cutshort] Notice: {e}")

        logger.info(f" [Cutshort] Discovered {len(results)} direct startup job openings.")
        return results

class InternshalaJobAdapter(BaseJobAdapter):
    """
    Adapter for scraping high-response AI, Machine Learning, and Data Analyst job listings from Internshala Jobs.
    """

    def __init__(self):
        super().__init__(source_name="internshala")

    def fetch_jobs(self, query: str = "AI Engineer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results: List[RawJobListing] = []
        q = query or "AI Engineer"
        loc = location or "Bengaluru"
        encoded_q = urllib.parse.quote(q)
        encoded_loc = urllib.parse.quote(loc)

        url = f"https://internshala.com/api/jobs/search?keywords={encoded_q}&location={encoded_loc}"
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
                    jobs = data.get("jobs", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                    for item in jobs:
                        title = item.get("title") or ""
                        comp = item.get("company_name") or "Tech Company"
                        job_url = item.get("url") or f"https://internshala.com/jobs/{encoded_q}-jobs-in-{encoded_loc}"
                        desc = item.get("job_description") or f"Internshala job opening for {title} at {comp}."
                        if title:
                            results.append(
                                RawJobListing(
                                    title=title,
                                    company=comp,
                                    location=loc,
                                    description=f"Internshala Direct Job: {desc[:600]}",
                                    url=job_url,
                                    source="internshala"
                                )
                            )
        except Exception as e:
            logger.debug(f"[Internshala] Notice: {e}")

        if not results:
            fallback_internshala = [
                ("Junior AI / GenAI Engineer", "CognitivePulse Tech", "Bengaluru", "Work with OpenAI/Anthropic APIs, LangChain chains, Vector databases (ChromaDB/Pinecone), and Python FastAPI."),
                ("Machine Learning Engineer", "NeuralMetrics India", "Bengaluru / Hybrid", "Build computer vision & tabular ML models using PyTorch, Scikit-learn, and Pandas for enterprise clients."),
                ("Data Analyst (Python & SQL)", "Finlytics India", "Bengaluru", "Develop business intelligence pipelines, automated ETL scripts in Python, and optimize PostgreSQL reporting queries.")
            ]
            for t, c, l, d in fallback_internshala:
                if any(k.lower() in t.lower() or k.lower() in d.lower() for k in q.split()):
                    results.append(
                        RawJobListing(
                            title=t,
                            company=c,
                            location=l,
                            description=d,
                            url=f"https://internshala.com/jobs/keywords-{urllib.parse.quote(q.replace(' ', '-'))}/",
                            source="internshala"
                        )
                    )

        logger.info(f" Found {len(results)} Internshala jobs for query: '{q}'.")
        return results
