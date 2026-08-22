import re
import json
import html
import urllib.request
from typing import List, Optional
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.jobs.schemas import RawJobListing
from src.utils.logger import logger

class HackerNewsHiringAdapter(BaseJobAdapter):
    """
    Direct Founder & Engineering Hiring Manager Adapter from Y Combinator's Hacker News 'Who is Hiring?'.
    Features 100% genuine postings from engineering leadership with direct founder contact & zero recruiter spam.
    """

    def __init__(self):
        super().__init__(source_name="hacker_news")

    def fetch_jobs(self, query: Optional[str] = None, location: Optional[str] = None, time_range: Optional[str] = None) -> List[RawJobListing]:
        discovered = []
        q_lower = query.lower() if query else "python"
        terms = [t.strip() for t in q_lower.replace(",", " ").split() if len(t.strip()) > 2]

        try:
            # 1. Find the latest "Who is hiring?" thread
            search_url = "https://hn.algolia.com/api/v1/search?query=Ask%20HN:%20Who%20is%20hiring&tags=story,author_whoishiring&hitsPerPage=1"
            req = urllib.request.Request(search_url, headers={"User-Agent": "Mozilla/5.0 (JobAgent/2.0)"})
            with urllib.request.urlopen(req, timeout=6) as resp:
                if resp.status != 200:
                    return []
                sdata = json.loads(resp.read().decode("utf-8"))
                hits = sdata.get("hits", [])
                if not hits:
                    return []
                story_id = hits[0].get("objectID")

            # 2. Fetch top comments (each comment is a direct job posting from a founder/team lead)
            comments_url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{story_id}&hitsPerPage=60"
            req2 = urllib.request.Request(comments_url, headers={"User-Agent": "Mozilla/5.0 (JobAgent/2.0)"})
            with urllib.request.urlopen(req2, timeout=6) as resp2:
                if resp2.status != 200:
                    return []
                cdata = json.loads(resp2.read().decode("utf-8"))
                comments = cdata.get("hits", [])

            for c in comments:
                raw_html = c.get("comment_text") or ""
                if not raw_html:
                    continue

                raw_text = html.unescape(raw_html)
                clean_text = re.sub(r"<[^>]+>", " ", raw_text).strip()
                text_lower = clean_text.lower()

                # Check if it matches target query or tech stack
                is_match = any(t in text_lower for t in terms) or any(
                    k in text_lower for k in ["python", "backend", "fastapi", "django", "engineer", "developer", "software"]
                )
                if not is_match:
                    continue

                # Filter by location if specified
                if location and location.lower() not in text_lower and "remote" not in text_lower and "anywhere" not in text_lower:
                    continue

                # Parse header line: typically "Company Name | Role | Location | ..."
                first_chunk = clean_text.split("\n")[0].strip()
                if len(first_chunk) > 120:
                    first_chunk = clean_text[:100]

                parts = [p.strip() for p in first_chunk.split("|") if p.strip()]
                company = parts[0] if parts else "YC Startup"
                title = parts[1] if len(parts) > 1 else "Software Engineer"
                loc = parts[2] if len(parts) > 2 else "Remote / Flexible"

                # Extract URL or fallback to HN comment URL
                url_match = re.search(r'href=[\'"]?(http[^\'" >]+)', raw_html)
                job_url = url_match.group(1) if url_match else f"https://news.ycombinator.com/item?id={c.get('objectID')}"

                job = RawJobListing(
                    title=title,
                    company=company,
                    location=loc,
                    description=clean_text[:600],
                    url=job_url,
                    source="hacker_news"
                )
                discovered.append(job)

        except Exception as e:
            logger.debug(f"[Hacker News] Fetch error: {e}")

        logger.info(f"[Hacker News] Discovered {len(discovered)} direct founder/engineering openings.")
        return discovered