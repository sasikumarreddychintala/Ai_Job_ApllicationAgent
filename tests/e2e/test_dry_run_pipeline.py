import pytest
from pathlib import Path
from config import settings
from src.database.models import init_db
from src.database.audit import AuditManager
from src.resume.validator import CandidateProfile, ContactInfo, WorkExperience, Education
from src.resume.profile import ProfileManager
from src.jobs.schemas import RawJobListing
from src.jobs.source_adapters.base_adapter import BaseJobAdapter
from src.jobs.finder import JobFinder
from src.agents.orchestrator import ApplicationOrchestrator

class DummyFormAdapter(BaseJobAdapter):
    def __init__(self, dummy_html_url: str):
        super().__init__(source_name="dummy_form")
        self.dummy_html_url = dummy_html_url

    def fetch_jobs(self, query: str = "", location: str = ""):
        return [
            RawJobListing(
                title="Python Backend Developer",
                company="DataFlow Systems",
                location="Remote",
                url=self.dummy_html_url,
                source="dummy_form",
                description="""
                Looking for a Python Backend Developer with experience in Python, FastAPI, Docker, and PostgreSQL.
                Work authorization without sponsorship required.
                """
            )
        ]

def test_end_to_end_dry_run_pipeline(tmp_path, monkeypatch):
    # 1. Setup isolated directories & paths
    db_file = tmp_path / "e2e_dry_run.db"
    prof_file = tmp_path / "candidate_profile.json"
    master_dir = tmp_path / "master_resume"
    tailored_dir = tmp_path / "tailored_resumes"
    logs_dir = tmp_path / "logs"
    
    dummy_html = Path(__file__).resolve().parent.parent / "browser" / "dummy_app.html"
    assert dummy_html.exists()
    dummy_url = dummy_html.as_uri()

    # Force DRY_RUN = True
    monkeypatch.setattr(settings, "DRY_RUN", True)
    monkeypatch.setattr(settings, "INSPECTION_PAUSE_SECONDS", 0)
    monkeypatch.setattr(settings, "DATABASE_PATH", db_file)
    monkeypatch.setattr(settings, "TAILORED_RESUMES_DIR", tailored_dir)
    monkeypatch.setattr(settings, "LOGS_DIR", logs_dir)

    # 2. Save candidate profile
    pm = ProfileManager(profile_path=prof_file, master_dir=master_dir)
    profile = CandidateProfile(
        contact_info=ContactInfo(
            full_name="Hemanth Kumar",
            email="hemanth@example.com",
            phone="+1-555-0199",
            location="Remote",
            linkedin="https://linkedin.com/in/hemanth"
        ),
        skills=["Python", "FastAPI", "Docker", "PostgreSQL", "Playwright", "Ollama"],
        experience=[
            WorkExperience(
                company="Tech Labs",
                position="Senior Python Developer",
                start_date="2021",
                end_date="Present",
                highlights=["Designed FastAPI backend services", "Deployed Docker containers"],
                verified_skills=["Python", "FastAPI", "Docker", "PostgreSQL"]
            )
        ],
        education=[Education(institution="UW", degree="B.S. CS", graduation_year="2021")],
        custom_answers={"work_authorization": "Authorized to work in US without sponsorship"}
    )
    pm.save_profile(profile)

    # 3. Initialize custom finder with DummyFormAdapter
    custom_adapter = DummyFormAdapter(dummy_url)
    finder = JobFinder(adapters=[custom_adapter], db_path=db_file)
    discovered = finder.discover_jobs()
    assert len(discovered) == 1

    # 4. Run Orchestrator Pipeline
    orchestrator = ApplicationOrchestrator(db_path=db_file, finder=finder)
    orchestrator.profile_manager = pm
    
    result = orchestrator.run_pipeline(max_applications=1)
    assert result["status"] == "SUCCESS"
    assert result["processed"] == 1

    # 5. Verify Database State & Audit History
    audit = AuditManager(db_path=db_file)
    history = audit.get_application_history()
    assert len(history) >= 1
    
    ready_apps = [h for h in history if h["status"] == "READY_TO_SUBMIT"]
    assert len(ready_apps) >= 1
    
    app_record = ready_apps[0]
    assert app_record["status"] == "READY_TO_SUBMIT"  # Confirms stopped BEFORE submit in DRY_RUN mode
    assert app_record["match_score"] is not None
    assert app_record["tailored_resume_path"] is not None
    assert Path(app_record["tailored_resume_path"]).exists()

    events = audit.get_application_events(app_record["job_id"])
    event_types = [e["event_type"] for e in events]
    assert "APPLICATION_STARTED" in event_types
    assert "FORM_FILLED" in event_types
