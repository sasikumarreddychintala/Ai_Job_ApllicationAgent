import re
from src.jobs.schemas import RawJobListing, NormalizedJob
from src.jobs.deduplicator import generate_job_fingerprint

def normalize_job_listing(raw_job: RawJobListing) -> NormalizedJob:
    """Normalizes raw job fields and attaches a stable cryptographic fingerprint."""
    clean_title = re.sub(r"\s+", " ", raw_job.title).strip()
    clean_company = re.sub(r"\s+", " ", raw_job.company).strip()
    clean_location = re.sub(r"\s+", " ", raw_job.location or "Remote").strip()
    clean_description = raw_job.description.strip()
    
    fingerprint = generate_job_fingerprint(clean_company, clean_title, raw_job.url, clean_location)
    
    return NormalizedJob(
        fingerprint=fingerprint,
        title=clean_title,
        company=clean_company,
        location=clean_location,
        description=clean_description,
        url=raw_job.url.strip(),
        source=raw_job.source.strip()
    )
