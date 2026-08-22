import pytest
import sqlite3
from pathlib import Path
import fitz  # PyMuPDF

from src.database.models import init_db
from src.resume.validator import CandidateProfile, ContactInfo, WorkExperience, Education
from src.resume.profile import ProfileManager
from src.ai.schemas import TailoredResumeOutput, TailoredBulletPoint
from src.resume.versioning import generate_pdf_resume, create_resume_version_filename
from src.jobs.source_adapters.local_fixture_adapter import LocalFixtureAdapter
from src.jobs.finder import JobFinder
from src.agents.jd_agent import JDAgent
from src.agents.match_agent import MatchAgent
from src.agents.resume_agent import ResumeTailorAgent

def test_pdf_resume_compilation(tmp_path):
    output_pdf = tmp_path / "test_resume.pdf"
    profile = CandidateProfile(
        contact_info=ContactInfo(full_name="Jane Doe", email="jane@example.com", location="Seattle, WA"),
        summary="Senior Software Engineer",
        skills=["Python", "FastAPI", "React", "Docker"],
        experience=[
            WorkExperience(
                company="TechCorp",
                position="Lead Engineer",
                start_date="2020",
                end_date="Present",
                highlights=["Architected cloud systems"],
                verified_skills=["Python", "Docker"]
            )
        ],
        education=[Education(institution="UW", degree="B.S. CS", graduation_year="2020")]
    )
    tailored = TailoredResumeOutput(
        summary="Senior Software Engineer specializing in Python and FastAPI",
        highlighted_skills=["Python", "FastAPI"],
        revised_bullet_points=[TailoredBulletPoint(original="Architected cloud systems", tailored="Architected cloud systems with Python")],
        truth_verified=True
    )
    
    pdf_path = generate_pdf_resume(profile, tailored, output_pdf)
    assert pdf_path.exists()
    assert pdf_path.stat().st_size > 0
    
    # Read PDF text
    doc = fitz.open(pdf_path)
    text = "".join(page.get_text() for page in doc)
    doc.close()
    
    assert "Jane Doe" in text
    assert "jane@example.com" in text
    assert "Python" in text

def test_resume_agent_tailor_pipeline(tmp_path):
    db_file = tmp_path / "test_tailor.db"
    prof_file = tmp_path / "candidate_profile.json"
    master_dir = tmp_path / "master_resume"
    out_dir = tmp_path / "tailored_resumes"
    
    # Save candidate profile
    pm = ProfileManager(profile_path=prof_file, master_dir=master_dir)
    profile = CandidateProfile(
        contact_info=ContactInfo(full_name="Hemanth Kumar", email="hemanth@example.com", location="Remote"),
        skills=["Python", "FastAPI", "React", "Ollama", "Docker", "PostgreSQL", "Playwright"],
        experience=[
            WorkExperience(
                company="Tech Corp",
                position="Senior AI Engineer",
                start_date="2021",
                end_date="Present",
                highlights=["Built AI workflows"],
                verified_skills=["Python", "FastAPI", "React", "Ollama", "Docker", "PostgreSQL", "Playwright"]
            )
        ],
        education=[Education(institution="UW", degree="B.S. CS", graduation_year="2021")],
        custom_answers={"work_authorization": "Authorized to work in US without sponsorship"}
    )
    pm.save_profile(profile)
    
    # 1. Discover jobs -> 2. Analyze JDs -> 3. Match Jobs (Qualifies jobs)
    finder = JobFinder(adapters=[LocalFixtureAdapter()], db_path=db_file)
    finder.discover_jobs()
    
    jd_agent = JDAgent(db_path=db_file)
    jd_agent.analyze_all_pending_jobs()
    
    match_agent = MatchAgent(profile_manager=pm, db_path=db_file)
    match_agent.evaluate_all_pending_jobs()
    
    # 4. Tailor Resumes for QUALIFIED jobs
    tailor_agent = ResumeTailorAgent(profile_manager=pm, output_dir=out_dir, db_path=db_file)
    tailored_paths = tailor_agent.tailor_all_pending_jobs()
    assert len(tailored_paths) >= 1
    assert all(p.exists() for p in tailored_paths)
    
    # 5. Verify SQLite records updated to RESUME_READY state
    conn = init_db(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT status, resume_version_id FROM applications WHERE status = 'RESUME_READY'")
    rows = cursor.fetchall()
    assert len(rows) == len(tailored_paths)
    assert all(r[1] is not None for r in rows)
    
    cursor.execute("SELECT COUNT(*) FROM resume_versions")
    version_count = cursor.fetchone()[0]
    assert version_count == len(tailored_paths)
    conn.close()
