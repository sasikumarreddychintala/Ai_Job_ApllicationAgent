import re
import urllib.request
import urllib.parse
from typing import List
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.utils.logger import logger


class HasjobAdapter(BaseJobAdapter):
    """Fetches live developer & AI opportunities from Hasjob (HasGeek) via their RSS feed.
    The old /api/1/jobs JSON endpoint no longer exists; we parse the Atom/RSS feed instead.
    """

    # Hasjob RSS feed — publicly accessible, no auth required
    RSS_URL = "https://hasjob.co/feed"

    def __init__(self):
        super().__init__(source_name="hasjob")

    def fetch_jobs(self, query: str = "Python Developer", location: str = "Bengaluru", time_range: str = "3d") -> List[RawJobListing]:
        results = []
        try:
            req = urllib.request.Request(
                self.RSS_URL,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; JobAgent/1.0)",
                    "Accept": "application/rss+xml, application/xml, text/xml, */*"
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml = resp.read().decode("utf-8", errors="ignore")

            # Parse <entry> (Atom) or <item> (RSS) blocks
            # Hasjob uses Atom format
            entries = re.findall(r"<entry>(.*?)</entry>", xml, re.DOTALL)
            if not entries:
                # Fallback: try RSS <item> tags
                entries = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)

            query_lower = (query or "").lower()

            for entry in entries[:30]:
                title = _extract_tag(entry, "title") or ""
                job_url = _extract_link(entry)
                company = _extract_tag(entry, "author") or _extract_tag(entry, "dc:creator") or "Company"
                summary = _extract_tag(entry, "summary") or _extract_tag(entry, "description") or ""
                job_location = _extract_tag(entry, "location") or location

                if not title or not job_url:
                    continue

                # Soft relevance filter: only include if query term matches title or summary
                combined = (title + " " + summary).lower()
                query_words = [w for w in query_lower.split() if len(w) > 3]
                if query_words and not any(w in combined for w in query_words):
                    continue

                results.append(RawJobListing(
                    title=title.strip(),
                    company=company.strip(),
                    location=job_location.strip(),
                    description=summary.strip() or f"Job: {title} at {company}",
                    url=job_url.strip(),
                    source="hasjob"
                ))

            logger.info(f" Hasjob adapter fetched {len(results)} live listings via RSS.")
        except Exception as e:
            logger.warning(f"Hasjob adapter notice: {e}")
        return results


# ── helpers ────────────────────────────────────────────────────────────────

def _extract_tag(text: str, tag: str) -> str:
    """Extracts inner text of the first occurrence of <tag>...</tag>, stripping CDATA."""
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", text, re.DOTALL | re.IGNORECASE)
    if not m:
        return ""
    val = m.group(1).strip()
    # Strip CDATA wrappers
    val = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", val, flags=re.DOTALL).strip()
    # Strip any remaining HTML tags for description
    val = re.sub(r"<[^>]+>", " ", val).strip()
    return val


def _extract_link(entry: str) -> str:
    """Extracts the job URL: tries <link href="..."/> (Atom) then <link>...</link> (RSS)."""
    # Atom: <link href="https://..." rel="alternate" .../>
    m = re.search(r'<link[^>]+href=["\']([^"\']+)["\']', entry, re.IGNORECASE)
    if m:
        return m.group(1)
    # RSS: <link>https://...</link>
    m = re.search(r"<link>(https?://[^<]+)</link>", entry, re.IGNORECASE)
    if m:
        return m.group(1)
    return ""
