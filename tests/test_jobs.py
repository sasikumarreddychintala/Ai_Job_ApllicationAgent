import pytest
import sqlite3
from src.database.models import init_db
from src.jobs.schemas import RawJobListing
from src.jobs.deduplicator import generate_job_fingerprint, is_job_duplicate
from src.jobs.normalizer import normalize_job_listing
from src.jobs.source_adapters.local_fixture_adapter import LocalFixtureAdapter
from src.jobs.finder import JobFinder

def test_fingerprint_generation_stability():
    fp1 = generate_job_fingerprint("Acme Corp", "Senior Python Engineer", "https://example.com/job/101?ref=linkedin")
    fp2 = generate_job_fingerprint("ACME CORP ", " senior python engineer", "https://example.com/job/101")
    assert fp1 == fp2

def test_job_normalization():
    raw = RawJobListing(
        title="  Senior AI   Engineer ",
        company=" Acme Inc ",
        location=" Remote ",
        description=" Great python job ",
        url="https://example.com/job/1",
        source="test"
    )
    norm = normalize_job_listing(raw)
    assert norm.title == "Senior AI Engineer"
    assert norm.company == "Acme Inc"
    assert norm.location == "Remote"
    assert len(norm.fingerprint) == 64

def test_job_finder_discovery_and_deduplication(tmp_path):
    db_file = tmp_path / "test_jobs.db"
    
    adapter = LocalFixtureAdapter()
    finder = JobFinder(adapters=[adapter], db_path=db_file)
    
    # First run: LocalFixtureAdapter has 2 jobs but one is "Senior Full Stack AI Engineer"
    # which is now correctly blocked by the title pre-filter before DB save.
    discovered = finder.discover_jobs()
    assert len(discovered) == 1  # Only the non-senior job passes the pre-filter
    
    # Second run with same adapter should detect the 1 saved job as duplicate → 0 new
    discovered_retry = finder.discover_jobs()
    assert len(discovered_retry) == 0
    
    # Verify DB contents: only 1 job saved (the non-senior one)
    conn = init_db(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM jobs")
    job_count = cursor.fetchone()[0]
    assert job_count == 1
    
    cursor.execute("SELECT COUNT(*) FROM applications WHERE status = 'DISCOVERED'")
    app_count = cursor.fetchone()[0]
    assert app_count == 1
    conn.close()
