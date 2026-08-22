import pytest
import sqlite3
from src.database.models import init_db
from src.resume.validator import CandidateProfile, ContactInfo
from src.ai.schemas import ParsedJDRequirements
from src.matching.rules import check_hard_constraints
from src.matching.scorer import calculate_match_score, normalize_skill
from src.jobs.source_adapters.local_fixture_adapter import LocalFixtureAdapter
from src.jobs.finder import JobFinder
from src.agents.jd_agent import JDAgent
from src.resume.profile import ProfileManager
from src.agents.match_agent import MatchAgent

def test_skill_alias_normalization():
    assert normalize_skill("JS") == "javascript"
    assert normalize_skill("Py ") == "python"
    assert normalize_skill("Postgres") == "postgresql"

def test_hard_constraint_violation():
    profile = CandidateProfile(
        contact_info=ContactInfo(full_name="John Doe", email="john@example.com"),
        skills=["Python"],
        custom_answers={"work_authorization": "H1B Visa - Requires Sponsorship"}
    )
    requirements = ParsedJDRequirements(
        title="Software Engineer",
        company="GovTech",
        location="Remote",
        required_skills=["Python"],
        hard_constraints=["US Citizenship Required"]
    )
    
    violated, reason = check_hard_constraints(profile, requirements)
    assert violated is True
    assert "Hard constraint failed" in reason
    
    eval_res = calculate_match_score(profile, requirements)
    assert eval_res.overall_score == 0
    assert eval_res.decision == "SKIP"
    assert eval_res.hard_constraint_violated is True

def test_match_agent_pipeline(tmp_path):
    db_file = tmp_path / "test_match.db"
    prof_file = tmp_path / "candidate_profile.json"
    master_dir = tmp_path / "master_resume"
    
    # Save candidate profile
    pm = ProfileManager(profile_path=prof_file, master_dir=master_dir)
    from src.resume.validator import WorkExperience, Education, Project
    profile = CandidateProfile(
        contact_info=ContactInfo(full_name="Hemanth Kumar", email="hemanth@example.com", location="Remote"),
        skills=["Python", "FastAPI", "React", "Ollama", "Docker", "PostgreSQL", "Playwright"],
        experience=[
            WorkExperience(
                company="Tech Corp",
                position="Senior AI Engineer",
                start_date="2021",
                end_date="Present",
                is_current=True,
                highlights=["Built AI workflows"],
                verified_skills=["Python", "FastAPI", "React", "Ollama", "Docker", "PostgreSQL", "Playwright"]
            ),
            WorkExperience(
                company="Data Solutions",
                position="Software Engineer",
                start_date="2019",
                end_date="2021",
                is_current=False,
                highlights=["Backend Python development"],
                verified_skills=["Python", "SQL"]
            )
        ],
        education=[Education(institution="University of Washington", degree="B.S. Computer Science", graduation_year="2019")],
        projects=[Project(name="Job Agent", description="AI agent", technologies=["Python", "FastAPI"])],
        custom_answers={"work_authorization": "Authorized to work in US without sponsorship"}
    )
    pm.save_profile(profile)
    
    # 1. Discover jobs
    adapter = LocalFixtureAdapter()
    finder = JobFinder(adapters=[adapter], db_path=db_file)
    finder.discover_jobs()
    
    # 2. Analyze JDs
    jd_agent = JDAgent(db_path=db_file)
    jd_agent.analyze_all_pending_jobs()
    
    # 3. Match Jobs
    match_agent = MatchAgent(profile_manager=pm, db_path=db_file)
    evals = match_agent.evaluate_all_pending_jobs()
    assert len(evals) == 2
    assert all(e.overall_score >= 70 for e in evals)
    assert all(e.decision in ["APPLY", "HIGH", "VERY_HIGH"] for e in evals)
    
    # 4. Verify SQLite application states updated to QUALIFIED
    conn = init_db(db_file)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM applications")
    statuses = [row[0] for row in cursor.fetchall()]
    assert all(s == "QUALIFIED" for s in statuses)
    
    cursor.execute("SELECT COUNT(*) FROM job_matches")
    match_count = cursor.fetchone()[0]
    assert match_count == 2
    conn.close()
