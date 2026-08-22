import pytest
from src.ai.schemas import (
    ParsedJDRequirements, MatchEvaluation, MatchScoreBreakdown,
    TailoredResumeOutput, TailoredBulletPoint, ApplicationAnswerOutput
)
from src.ai.prompts.jd_prompt import render_jd_prompt
from src.ai.prompts.match_prompt import render_match_prompt
from src.ai.prompts.tailor_prompt import render_tailor_prompt
from src.ai.prompts.answer_prompt import render_answer_prompt
from src.ai.ollama_client import OllamaClient

def test_parsed_jd_schema():
    jd = ParsedJDRequirements(
        title="Senior Python Engineer",
        company="Acme Corp",
        location="Remote",
        min_years_experience=5,
        required_skills=["Python", "FastAPI", "SQL"],
        preferred_skills=["Docker", "AWS"]
    )
    assert jd.title == "Senior Python Engineer"
    assert jd.min_years_experience == 5
    assert "Python" in jd.required_skills

def test_match_evaluation_schema():
    breakdown = MatchScoreBreakdown(
        required_skills_score=35,
        experience_fit_score=20,
        project_relevance_score=15,
        technical_similarity_score=15,
        education_score=5,
        location_score=5,
        other_factors_score=5
    )
    match_eval = MatchEvaluation(
        overall_score=100,
        decision="VERY_HIGH",
        score_breakdown=breakdown,
        matched_skills=["Python", "FastAPI"],
        missing_required_skills=[],
        hard_constraint_violated=False,
        reasoning="Perfect candidate match"
    )
    assert match_eval.overall_score == 100
    assert match_eval.decision == "VERY_HIGH"

def test_prompt_formatting():
    jd_prompt = render_jd_prompt("Software Engineer job")
    assert "Software Engineer job" in jd_prompt
    
    answer_prompt = render_answer_prompt(
        question="What is your work authorization?",
        profile_json="{}"
    )
    assert "What is your work authorization?" in answer_prompt

def test_ollama_client_online_check():
    client = OllamaClient()
    is_online = client.is_online()
    assert isinstance(is_online, bool)
