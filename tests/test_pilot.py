import pytest
from pathlib import Path
from src.resume.validator import CandidateProfile, ContactInfo, WorkExperience, Education
from src.resume.profile import ProfileManager
from src.automation.pilot import PilotRunner
from src.database.models import init_db

def test_pilot_runner_dry_run_and_live(tmp_path):
    db_file = tmp_path / "test_pilot.db"
    prof_file = tmp_path / "candidate_profile.json"
    master_dir = tmp_path / "master_resume"
    tailored_dir = tmp_path / "tailored_resumes"
    
    dummy_html = Path(__file__).resolve().parent / "browser" / "dummy_app.html"
    assert dummy_html.exists()
    dummy_url = f"file:///{str(dummy_html).replace('\\', '/')}"

    # Setup Candidate Profile
    pm = ProfileManager(profile_path=prof_file, master_dir=master_dir)
    profile = CandidateProfile(
        contact_info=ContactInfo(
            full_name="Hemanth Kumar",
            email="hemanth@example.com",
            phone="+1-555-0199",
            location="Remote",
            linkedin="https://linkedin.com/in/hemanth"
        ),
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "Playwright"],
        experience=[
            WorkExperience(
                company="Tech AI",
                position="Senior Python Developer",
                start_date="2021",
                end_date="Present",
                highlights=["FastAPI development"],
                verified_skills=["Python", "FastAPI", "PostgreSQL", "Docker"]
            )
        ],
        education=[Education(institution="UW", degree="B.S. CS", graduation_year="2021")],
        custom_answers={"work_authorization": "Authorized to work in US without sponsorship"}
    )
    pm.save_profile(profile)

    runner = PilotRunner(db_path=db_file)
    runner.profile_manager = pm

    # 1. Run Dry-Run Pilot
    res_dry = runner.run_pilot_on_url(dummy_url, is_live_submission=False)
    assert res_dry["status"] == "SUCCESS"
    assert res_dry["application_status"] == "READY_TO_SUBMIT"

    # Verify in DB
    conn = init_db(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM applications WHERE job_id = ?", (res_dry["job_id"],))
    assert cursor.fetchone()[0] == "READY_TO_SUBMIT"
    conn.close()
