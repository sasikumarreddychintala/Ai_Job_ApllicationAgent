import pytest
import sqlite3
from src.database.models import init_db
from src.jobs.schemas import RawJobListing
from src.jobs.normalizer import normalize_job_listing
from src.jobs.finder import JobFinder
from src.jobs.source_adapters.local_fixture_adapter import LocalFixtureAdapter
from src.agents.jd_agent import JDAgent

def test_fallback_parse_jd():
    agent = JDAgent()
    raw_jd = "Senior Python Developer role requiring Python, FastAPI, Docker, and US Citizenship."
    reqs = agent._fallback_parse_jd(raw_jd, "Senior Python Developer", "Acme", "Remote")
    
    assert reqs.title == "Senior Python Developer"
    assert "Python" in reqs.required_skills
    assert "FastAPI" in reqs.required_skills
    assert len(reqs.hard_constraints) > 0

def test_jd_agent_analyze_job(tmp_path):
    db_file = tmp_path / "test_jd_agent.db"
    
    # 1. Discover a job to insert DISCOVERED state into DB
    adapter = LocalFixtureAdapter()
    finder = JobFinder(adapters=[adapter], db_path=db_file)
    discovered = finder.discover_jobs()
    assert len(discovered) == 2
    
    # 2. Run JDAgent analyze_all_pending_jobs
    jd_agent = JDAgent(db_path=db_file)
    analyzed = jd_agent.analyze_all_pending_jobs()
    assert len(analyzed) == 2
    
    # 3. Verify SQLite records updated to ANALYZED state
    conn = init_db(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM applications")
    statuses = [row[0] for row in cursor.fetchall()]
    assert all(s == "ANALYZED" for s in statuses)
    
    cursor.execute("SELECT analyzed_requirements FROM jobs")
    reqs_jsons = [row[0] for row in cursor.fetchall()]
    assert all(req is not None for req in reqs_jsons)
    conn.close()
