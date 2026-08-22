import pytest
import sqlite3
from src.database.models import init_db
from src.resume.validator import CandidateProfile, ContactInfo
from src.resume.profile import ProfileManager
from src.automation.question_classifier import classify_question, QuestionCategory
from src.agents.answer_agent import ApplicationAnswerAgent, hash_question

def test_question_classification():
    assert classify_question("What is your full name?") == QuestionCategory.FULL_NAME
    assert classify_question("What is your email address?") == QuestionCategory.EMAIL
    assert classify_question("Are you legally authorized to work in the United States?") == QuestionCategory.WORK_AUTHORIZATION
    assert classify_question("What is your expected salary range?") == QuestionCategory.SALARY_EXPECTATION
    assert classify_question("Why do you want to work at our company?") == QuestionCategory.CUSTOM_OPEN_ENDED

def test_answer_known_profile_fields(tmp_path):
    prof_file = tmp_path / "candidate_profile.json"
    master_dir = tmp_path / "master_resume"
    db_file = tmp_path / "test_answer.db"
    
    pm = ProfileManager(profile_path=prof_file, master_dir=master_dir)
    profile = CandidateProfile(
        contact_info=ContactInfo(
            full_name="Hemanth Kumar",
            email="hemanth@example.com",
            phone="+1-555-0199",
            location="Seattle, WA",
            linkedin="https://linkedin.com/in/hemanth"
        ),
        custom_answers={
            "work_authorization": "Authorized to work in US without sponsorship",
            "notice_period": "2 weeks"
        }
    )
    pm.save_profile(profile)
    
    agent = ApplicationAnswerAgent(profile_manager=pm, db_path=db_file)
    
    out_name = agent.answer_question("What is your full name?")
    assert out_name.answer == "Hemanth Kumar"
    assert out_name.is_known is True
    
    out_email = agent.answer_question("Please provide your email address:")
    assert out_email.answer == "hemanth@example.com"
    
    out_auth = agent.answer_question("Are you authorized to work in the US?")
    assert "Authorized to work" in out_auth.answer

def test_answer_reuse_from_database(tmp_path):
    prof_file = tmp_path / "candidate_profile.json"
    master_dir = tmp_path / "master_resume"
    db_file = tmp_path / "test_answer_db.db"
    
    pm = ProfileManager(profile_path=prof_file, master_dir=master_dir)
    profile = CandidateProfile(contact_info=ContactInfo(full_name="Jane", email="jane@example.com"))
    pm.save_profile(profile)
    
    agent = ApplicationAnswerAgent(profile_manager=pm, db_path=db_file)
    
    # Save approved answer
    question = "What is your preferred programming paradigm?"
    agent.record_user_approved_answer(question, "Functional and Object-Oriented Python")
    
    # Query answer
    out = agent.answer_question(question)
    assert out.answer == "Functional and Object-Oriented Python"
    assert out.is_known is True

def test_unknown_question_manual_review_trigger(tmp_path):
    prof_file = tmp_path / "candidate_profile.json"
    master_dir = tmp_path / "master_resume"
    db_file = tmp_path / "test_unknown.db"
    
    pm = ProfileManager(profile_path=prof_file, master_dir=master_dir)
    profile = CandidateProfile(contact_info=ContactInfo(full_name="Alex", email="alex@example.com"))
    pm.save_profile(profile)
    
    agent = ApplicationAnswerAgent(profile_manager=pm, db_path=db_file)
    
    # Make sure Ollama offline simulation returns manual review flag
    agent.ollama.is_online = lambda: False
    
    out = agent.answer_question("What is your Security Clearance Number?")
    assert out.is_known is False
    assert out.requires_manual_review is True
