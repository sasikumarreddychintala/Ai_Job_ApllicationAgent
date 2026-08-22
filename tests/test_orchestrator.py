import pytest
import sqlite3
from pathlib import Path
from src.database.models import init_db
from src.resume.validator import CandidateProfile, ContactInfo, WorkExperience, Education
from src.resume.profile import ProfileManager
from src.agents.state_machine import validate_state_transition, ApplicationState
from src.agents.orchestrator import ApplicationOrchestrator
from src.jobs.source_adapters.local_fixture_adapter import LocalFixtureAdapter
from src.jobs.finder import JobFinder

def test_state_machine_transitions():
    # Valid transitions
    assert validate_state_transition("DISCOVERED", "ANALYZED") is True
    assert validate_state_transition("ANALYZED", "QUALIFIED") is True
    assert validate_state_transition("QUALIFIED", "RESUME_READY") is True
    assert validate_state_transition("FORM_FILLED", "READY_TO_SUBMIT") is True
    
    # Invalid transitions
    assert validate_state_transition("DISCOVERED", "SUBMITTED") is False
    assert validate_state_transition("SKIPPED", "QUALIFIED") is False

def test_orchestrator_pipeline_execution(tmp_path):
    db_file = tmp_path / "test_orch.db"
    prof_file = tmp_path / "candidate_profile.json"
    master_dir = tmp_path / "master_resume"
    
    # Save candidate profile
    pm = ProfileManager(profile_path=prof_file, master_dir=master_dir)
    profile = CandidateProfile(
        contact_info=ContactInfo(
            full_name="Hemanth Kumar",
            email="hemanth@example.com",
            location="Remote"
        ),
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
    
    orchestrator = ApplicationOrchestrator(db_path=db_file)
    orchestrator.profile_manager = pm
    
    # Run pipeline with limit=2
    res = orchestrator.run_pipeline(max_applications=2)
    assert res["status"] == "SUCCESS"
    assert res["discovered"] == 2
    assert res["qualified"] >= 1
    
    # Verify SQLite application states
    conn = init_db(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM applications WHERE status IN ('READY_TO_SUBMIT', 'SUBMITTED')")
    submitted_rows = cursor.fetchall()
    assert len(submitted_rows) >= 1
    conn.close()
