import re
from typing import List, Set
from config import settings
from src.resume.validator import CandidateProfile
from src.ai.schemas import ParsedJDRequirements, MatchEvaluation, MatchScoreBreakdown
from src.matching.rules import check_hard_constraints

SKILL_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "python3": "python",
    "postgres": "postgresql",
    "pg": "postgresql",
    "psql": "postgresql",
    "react.js": "react",
    "reactjs": "react",
    "node": "node.js",
    "nodejs": "node.js",
    "aws": "amazon web services",
    "gcp": "google cloud platform",
    "k8s": "kubernetes",
    "gen ai": "generative ai",
    "genai": "generative ai",
    "llm": "large language models",
    "llms": "large language models",
    "rag": "retrieval-augmented generation",
    "fast-api": "fastapi",
    "rest": "rest apis",
    "rest api": "rest apis",
    "restful": "rest apis",
    "db": "database",
    "ci/cd": "cicd",
    "ci-cd": "cicd",
    "bi": "business intelligence"
}

# Semantic Skill Clusters for Hybrid Matching
SKILL_CLUSTERS = {
    "python": {"python", "fastapi", "django", "flask", "asyncio", "celery", "pydantic", "sqlalchemy"},
    "generative ai": {"generative ai", "large language models", "retrieval-augmented generation", "langchain", "llamaindex", "crewai", "ollama", "groq", "openai", "embeddings", "vector databases", "transformers"},
    "postgresql": {"postgresql", "sql", "relational database", "mysql", "sqlite", "database design"},
    "docker": {"docker", "containerization", "kubernetes", "docker-compose"},
    "playwright": {"playwright", "selenium", "web automation", "browser automation", "scraping", "beautifulsoup"},
    "fastapi": {"fastapi", "rest apis", "microservices", "api development", "backend development"},
    "data analysis": {"data analysis", "pandas", "numpy", "powerbi", "tableau", "sql", "data pipelines"}
}

def normalize_skill(skill: str) -> str:
    """Normalizes skill strings for accurate semantic comparison."""
    clean = skill.lower().strip().replace("-", " ")
    clean = re.sub(r'\s+', ' ', clean)
    return SKILL_ALIASES.get(clean, clean)

def are_skills_semantically_related(skill_a: str, skill_b: str) -> bool:
    """Checks if two skills belong to the same technical cluster or domain."""
    norm_a = normalize_skill(skill_a)
    norm_b = normalize_skill(skill_b)
    if norm_a == norm_b or norm_a in norm_b or norm_b in norm_a:
        return True
    for cluster in SKILL_CLUSTERS.values():
        if norm_a in cluster and norm_b in cluster:
            return True
    return False

def calculate_match_score(
    candidate: CandidateProfile,
    requirements: ParsedJDRequirements
) -> MatchEvaluation:
    """
    Computes a transparent weighted match evaluation score between verified candidate profile facts
    and parsed JD requirements.
    """
    # 1. Check hard constraint rules first
    violated, reason = check_hard_constraints(candidate, requirements)
    if violated:
        breakdown = MatchScoreBreakdown(
            required_skills_score=0,
            experience_fit_score=0,
            project_relevance_score=0,
            technical_similarity_score=0,
            education_score=0,
            location_score=0,
            other_factors_score=0
        )
        return MatchEvaluation(
            overall_score=0,
            decision="SKIP",
            score_breakdown=breakdown,
            matched_skills=[],
            missing_required_skills=requirements.required_skills,
            hard_constraint_violated=True,
            reasoning=f"HARD CONSTRAINT VIOLATED: {reason}"
        )

    # 2. Skill Overlap Calculation (0-35 points)
    candidate_skills_set: Set[str] = {normalize_skill(s) for s in candidate.skills}
    # Add skills from experience highlights
    for exp in candidate.experience:
        for s in exp.verified_skills:
            candidate_skills_set.add(normalize_skill(s))

    req_skills = [s for s in requirements.required_skills if s.strip()]
    matched_skills = []
    missing_skills = []

    if req_skills:
        for req_s in req_skills:
            norm_req_s = normalize_skill(req_s)
            if norm_req_s in candidate_skills_set or any(norm_req_s in s for s in candidate_skills_set):
                matched_skills.append(req_s)
            else:
                missing_skills.append(req_s)
        match_ratio = len(matched_skills) / len(req_skills)
        required_skills_score = round(match_ratio * 35)
    else:
        required_skills_score = 35

    # 3. Experience Depth Fit (0-20 points)
    # Calculate candidate experience years from positions
    total_exp_years = 0.0
    for exp in candidate.experience:
        start_str = str(exp.start_date or "").strip().lower()
        end_str = str(exp.end_date or "present").strip().lower()
        
        # Check for year numbers in start and end
        start_years = re.findall(r'\b(20\d\d|19\d\d)\b', start_str)
        end_years = re.findall(r'\b(20\d\d|19\d\d)\b', end_str)
        
        if start_years and end_years:
            diff = int(end_years[0]) - int(start_years[0])
            total_exp_years += max(1.0, float(diff))
        elif start_years:
            # Started in recent year (e.g. 2025)
            total_exp_years += max(1.0, 2026 - int(start_years[0]) + 0.5)
        else:
            total_exp_years += 1.5

    min_years = float(requirements.min_years_experience or 0)
    title_lower = (getattr(requirements, "title", "") or "").lower()
    is_early_career = any(w in title_lower for w in ["fresher", "junior", "associate", "entry level", "graduate", "trainee", "intern"]) or min_years <= 2.0

    if is_early_career or min_years <= 2.0:
        # Perfect 0-2 Yrs / Fresher target fit
        experience_fit_score = 20
    elif min_years <= 3.0:
        experience_fit_score = 15
    else:
        # Penalize higher experience roles
        experience_fit_score = 5

    # 4. Project Relevance (0-15 points)
    if candidate.projects:
        project_relevance_score = 15 if len(candidate.projects) >= 2 else 10
    else:
        project_relevance_score = 5

    # 5. Technical Semantic Similarity (0-15 points)
    # Overlap between candidate summary/skills and JD keywords
    jd_keywords = set(normalize_skill(k) for k in requirements.keywords if k.strip())
    if jd_keywords:
        tech_matched = [k for k in jd_keywords if k in candidate_skills_set]
        tech_ratio = len(tech_matched) / len(jd_keywords)
        technical_similarity_score = round(tech_ratio * 15)
    else:
        technical_similarity_score = 12

    # 6. Education Fit (0-5 points)
    if candidate.education:
        education_score = 5
    else:
        education_score = 3

    # 7. Location Fit (0-5 points)
    cand_loc = (candidate.contact_info.location or "").lower()
    jd_loc = (requirements.location or "").lower()
    if "remote" in jd_loc or "remote" in cand_loc or jd_loc in cand_loc or cand_loc in jd_loc:
        location_score = 5
    else:
        location_score = 3

    # 8. Other Factors (0-5 points)
    other_factors_score = 5 if candidate.certifications else 4

    # Calculate Total Overall Score (0-100)
    total_score = (
        required_skills_score +
        experience_fit_score +
        project_relevance_score +
        technical_similarity_score +
        education_score +
        location_score +
        other_factors_score
    )
    total_score = min(100, max(0, total_score))

    # Map decision based on configurable thresholds
    if total_score < settings.MIN_MATCH_SCORE:
        decision = "SKIP"
    elif total_score < 80:
        decision = "APPLY"
    elif total_score < 90:
        decision = "HIGH"
    else:
        decision = "VERY_HIGH"

    breakdown = MatchScoreBreakdown(
        required_skills_score=required_skills_score,
        experience_fit_score=experience_fit_score,
        project_relevance_score=project_relevance_score,
        technical_similarity_score=technical_similarity_score,
        education_score=education_score,
        location_score=location_score,
        other_factors_score=other_factors_score
    )

    reasoning = (
        f"Match Score: {total_score}/100 ({decision}). "
        f"Matched {len(matched_skills)}/{len(req_skills) if req_skills else 1} required skills. "
        f"Missing required skills: {', '.join(missing_skills) if missing_skills else 'None'}."
    )

    return MatchEvaluation(
        overall_score=total_score,
        decision=decision,
        score_breakdown=breakdown,
        matched_skills=matched_skills,
        missing_required_skills=missing_skills,
        hard_constraint_violated=False,
        reasoning=reasoning
    )
