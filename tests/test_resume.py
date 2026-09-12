import pytest
import json
from pathlib import Path
from src.resume.validator import (
    CandidateProfile, ContactInfo, WorkExperience, Education, sanitize_sensitive_data
)
from src.resume.parser import parse_resume_with_ollama, create_fallback_profile
from src.resume.profile import ProfileManager

def test_sensitive_data_sanitization():
    raw_text = "John Doe, SSN: 123-45-6789, API key: sk-abcdef123456789012345678"
    sanitized = sanitize_sensitive_data(raw_text)
    assert "123-45-6789" not in sanitized
    assert "[REDACTED_SSN]" in sanitized
    assert "sk-abcdef123456789012345678" not in sanitized
    assert "[REDACTED_API_KEY]" in sanitized

def test_candidate_profile_schema_validation():
    profile = CandidateProfile(
        contact_info=ContactInfo(
            full_name="Alice Smith",
            email="alice@example.com",
            location="New York, NY"
        ),
        summary="Experienced Full Stack Developer",
        skills=["Python", "React", "TypeScript", "SQL"],
        experience=[
            WorkExperience(
                company="Tech Corp",
                position="Lead Engineer",
                start_date="2020",
                end_date="Present",
                is_current=True,
                highlights=["Built scalable API serving 500k users daily"],
                verified_skills=["Python", "SQL"]
            )
        ],
        education=[
            Education(
                institution="MIT",
                degree="B.S. Computer Science",
                graduation_year="2020"
            )
        ]
    )
    assert profile.contact_info.full_name == "Alice Smith"
    assert profile.contact_info.email == "alice@example.com"
    assert len(profile.skills) == 4
    assert profile.experience[0].company == "Tech Corp"

def test_fallback_profile_creation():
    sample_text = "Jane Doe\nEmail: jane.doe@example.org\nSoftware Engineer"
    profile = create_fallback_profile(sample_text)
    assert profile.contact_info.full_name == "Jane Doe"
    assert profile.contact_info.email == "jane.doe@example.org"

def test_profile_manager_save_and_load(tmp_path):
    profile_file = tmp_path / "candidate_profile.json"
    master_dir = tmp_path / "master_resume"
    
    pm = ProfileManager(profile_path=profile_file, master_dir=master_dir)
    
    profile = CandidateProfile(
        contact_info=ContactInfo(full_name="Bob Miller", email="bob@example.com"),
        skills=["Docker", "Kubernetes"]
    )
    
    pm.save_profile(profile)
    assert profile_file.exists()
    
    loaded = pm.load_profile()
    assert loaded is not None
    assert loaded.contact_info.full_name == "Bob Miller"
    assert "Docker" in loaded.skills


def test_pure_python_resume_parser():
    from src.resume.parser import PurePythonResumeParser, extract_resume_text
    sample_pdf = Path("data/sample_resume.pdf")
    if sample_pdf.exists():
        raw_text = extract_resume_text(sample_pdf)
        profile = PurePythonResumeParser.parse(raw_text)
        assert profile.contact_info.full_name == "Hemanth Kumar"
        assert profile.contact_info.email == "hemanth@example.com"
        assert "+1-555-0199" in profile.contact_info.phone
        assert "Seattle" in profile.contact_info.location
        assert profile.contact_info.linkedin is not None
        assert profile.contact_info.github is not None
        assert "Python" in profile.skills
        assert "FastAPI" in profile.skills
        assert len(profile.experience) >= 1
        assert "Tech Corp" in profile.experience[0].company
        assert len(profile.education) >= 1
        assert "University of Washington" in profile.education[0].institution


def test_resume_parser_class():
    from src.resume.parser import ResumeParser
    sample_pdf = Path("data/sample_resume.pdf")
    if sample_pdf.exists():
        parser = ResumeParser()
        profile = parser.parse(sample_pdf)
        assert profile.contact_info.full_name is not None
        assert len(profile.skills) > 0

def test_sanitize_pdf_text():
    from src.resume.versioning import sanitize_pdf_text
    # Unicode non-breaking hyphen (\u2011), en-dash (\u2013), em-dash (\u2014), minus (\u2212)
    sample = "high\u2011performance micro\u2013service event\u2014driven real\u2212time \u2018quotes\u2019 \u201csmart\u201d ■"
    cleaned = sanitize_pdf_text(sample)
    assert cleaned == 'high-performance micro-service event-driven real-time \'quotes\' "smart" '
    assert "\u2011" not in cleaned
    assert "■" not in cleaned


