import pytest
from src.resume.validator import CandidateProfile, ContactInfo, WorkExperience, Education
from src.resume.profile import ProfileManager
from src.rag.retriever import CandidateRAGStore
from src.agents.answer_agent import ApplicationAnswerAgent

def test_rag_store_indexing_and_retrieval(tmp_path):
    prof_file = tmp_path / "candidate_profile.json"
    master_dir = tmp_path / "master_resume"
    
    pm = ProfileManager(profile_path=prof_file, master_dir=master_dir)
    profile = CandidateProfile(
        contact_info=ContactInfo(
            full_name="Hemanth Kumar",
            email="hemanth@example.com"
        ),
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "Ollama", "Playwright"],
        experience=[
            WorkExperience(
                company="AI Automation Labs",
                position="Lead AI Engineer",
                start_date="2022",
                end_date="Present",
                highlights=["Engineered autonomous multi-agent pipelines with local LLMs and Playwright automation"],
                verified_skills=["Python", "Playwright", "Ollama"]
            ),
            WorkExperience(
                company="DataFlow Corp",
                position="Backend Developer",
                start_date="2020",
                end_date="2022",
                highlights=["Scaled PostgreSQL database queries and optimized FastAPI REST endpoints"],
                verified_skills=["FastAPI", "PostgreSQL", "Docker"]
            )
        ],
        education=[Education(institution="University of Washington", degree="B.S. Computer Science", graduation_year="2020")],
        custom_answers={"work_authorization": "US Citizen authorized to work without sponsorship"}
    )
    pm.save_profile(profile)

    rag = CandidateRAGStore(profile_manager=pm)
    assert len(rag._chunks) >= 4

    # Test targeted retrieval for agent workflows
    snippets_agent = rag.retrieve_relevant_context("Tell us about your experience building autonomous AI agents and Playwright automation", top_k=1)
    assert len(snippets_agent) == 1
    assert "AI Automation Labs" in snippets_agent[0]

    # Test targeted retrieval for database scaling
    snippets_db = rag.retrieve_relevant_context("Have you worked with PostgreSQL optimization and FastAPI?", top_k=1)
    assert len(snippets_db) == 1
    assert "DataFlow Corp" in snippets_db[0]
