import re
from datetime import datetime
from typing import List, Set, Optional
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
    "bi": "business intelligence",
    "ml": "machine learning",
    "nlp": "natural language processing",
    "dl": "deep learning",
    "mongo": "mongodb",
    "nosql": "nosql database",
    "kafka": "apache kafka",
}

# Semantic Skill Clusters for Hybrid Matching.
# IMPORTANT: Each skill must belong to AT MOST ONE cluster to prevent cross-cluster false matches.
# e.g. "java" and "javascript" are SEPARATE clusters — no shared members.
SKILL_CLUSTERS = {
    "python": {"python", "fastapi", "django", "flask", "asyncio", "celery", "pydantic", "sqlalchemy"},
    "generative ai": {"generative ai", "large language models", "retrieval-augmented generation", "langchain", "llamaindex", "crewai", "ollama", "groq", "openai", "embeddings", "vector databases", "transformers", "hugging face"},
    "postgresql": {"postgresql", "relational database", "mysql", "sqlite", "database design"},
    "docker": {"docker", "containerization", "kubernetes", "docker-compose"},
    "playwright": {"playwright", "selenium", "web automation", "browser automation", "scraping", "beautifulsoup"},
    "fastapi": {"fastapi", "rest apis", "microservices", "api development", "backend development"},
    "data analysis": {"data analysis", "pandas", "numpy", "powerbi", "tableau", "data pipelines"},
    "machine learning": {"machine learning", "deep learning", "pytorch", "tensorflow", "scikit-learn", "computer vision", "natural language processing"},
    # java and javascript are INTENTIONALLY SEPARATE clusters
    "java": {"java", "spring", "spring boot", "maven", "gradle", "jvm"},
    "javascript": {"javascript", "typescript", "node.js", "react", "vue", "angular"},
    "apache kafka": {"apache kafka", "event streaming", "event-driven", "message queue", "rabbitmq"},
    "mongodb": {"mongodb", "nosql database", "dynamodb", "cassandra"},
}

# City alias map for location matching accuracy (Bengaluru/Bangalore etc.)
CITY_ALIASES: dict = {
    "bengaluru": {"bengaluru", "bangalore", "blr", "bengalore", "bangaluru"},
    "mumbai": {"mumbai", "bombay", "mum"},
    "delhi": {"delhi", "new delhi", "ncr", "gurgaon", "gurugram", "noida", "faridabad"},
    "hyderabad": {"hyderabad", "hyd", "secunderabad", "cyberabad"},
    "pune": {"pune", "poona"},
    "chennai": {"chennai", "madras"},
    "kolkata": {"kolkata", "calcutta"},
}

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}


def normalize_skill(skill: str) -> str:
    """Normalizes skill strings for accurate semantic comparison."""
    clean = skill.lower().strip().replace("-", " ")
    clean = re.sub(r'\s+', ' ', clean)
    return SKILL_ALIASES.get(clean, clean)


def are_skills_semantically_related(skill_a: str, skill_b: str) -> bool:
    """
    Checks if two skills belong to the same technical cluster.
    Uses cluster membership only — NOT substring — to prevent false matches like java→javascript.
    """
    norm_a = normalize_skill(skill_a)
    norm_b = normalize_skill(skill_b)
    if norm_a == norm_b:
        return True
    for cluster in SKILL_CLUSTERS.values():
        if norm_a in cluster and norm_b in cluster:
            return True
    return False


def _parse_date_str(date_str: str) -> Optional[datetime]:
    """
    Parse date strings like 'Jul 2025', 'July 2024', '2025-07', '07/2025'.
    Returns datetime or None. 'present'/'current' returns today.
    """
    s = date_str.strip().lower()
    if not s or s in ("present", "current", "now", "ongoing", "till date"):
        return datetime.now()

    # "Month YYYY" e.g. "Jul 2025"
    m = re.match(r'([a-z]+)\s+(20\d\d|19\d\d)', s)
    if m:
        month_name, year = m.group(1), int(m.group(2))
        month = _MONTH_MAP.get(month_name[:3])
        if month:
            return datetime(year, month, 1)

    # "YYYY-MM" or "MM/YYYY"
    m = re.match(r'(20\d\d|19\d\d)[-/](0?[1-9]|1[0-2])', s)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), 1)
    m = re.match(r'(0?[1-9]|1[0-2])/(20\d\d|19\d\d)', s)
    if m:
        return datetime(int(m.group(2)), int(m.group(1)), 1)

    # Plain year "2025"
    m = re.match(r'\b(20\d\d|19\d\d)\b', s)
    if m:
        return datetime(int(m.group(1)), 7, 1)  # assume mid-year

    return None


def _compute_experience_years(candidate: CandidateProfile) -> float:
    """
    Month-aware experience calculation using datetime diff.
    Far more accurate than year-only subtraction (avoids ±11 month errors).
    """
    total_months = 0
    for exp in candidate.experience:
        start_str = str(exp.start_date or "").strip()
        end_str = str(exp.end_date or "present").strip()

        start_dt = _parse_date_str(start_str)
        end_dt = _parse_date_str(end_str)

        if start_dt and end_dt and end_dt >= start_dt:
            diff_months = (end_dt.year - start_dt.year) * 12 + (end_dt.month - start_dt.month)
            total_months += max(1, diff_months)
        else:
            total_months += 12  # fallback: assume 1 year

    return round(total_months / 12, 2)


def _location_matches(cand_loc: str, jd_loc: str) -> bool:
    """
    Location match using city alias map.
    Handles Bengaluru/Bangalore, Delhi/NCR, remote/hybrid keywords.
    """
    cand_lower = cand_loc.lower()
    jd_lower = jd_loc.lower()

    if not jd_lower or "remote" in jd_lower or "anywhere" in jd_lower or "worldwide" in jd_lower:
        return True
    if "remote" in cand_lower:
        return True
    if jd_lower in cand_lower or cand_lower in jd_lower:
        return True

    for canonical, aliases in CITY_ALIASES.items():
        cand_in_cluster = any(alias in cand_lower for alias in aliases)
        jd_in_cluster = any(alias in jd_lower for alias in aliases)
        if cand_in_cluster and jd_in_cluster:
            return True

    return False


def calculate_match_score(
    candidate: CandidateProfile,
    requirements: ParsedJDRequirements
) -> MatchEvaluation:
    """
    Computes a transparent weighted match evaluation score between verified candidate profile facts
    and parsed JD requirements.

    Score weights (total = 100):
      required_skills:       30 pts  (was 35 — freed 5 pts for preferred_skills)
      preferred_skills:       5 pts  [NEW]
      experience_fit:        20 pts
      project_relevance:     15 pts
      technical_similarity:  15 pts
      education:              5 pts
      location:               5 pts
      other_factors:          5 pts
    """
    # 1. Hard constraint check
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

    # 2. Build candidate skill set (profile + experience-verified skills)
    candidate_skills_set: Set[str] = {normalize_skill(s) for s in candidate.skills}
    for exp in candidate.experience:
        for s in exp.verified_skills:
            candidate_skills_set.add(normalize_skill(s))

    # 3. Required Skill Matching (0–30 pts)
    # FIX: Use exact match OR semantic cluster match ONLY.
    req_skills = [s for s in requirements.required_skills if s.strip()]
    matched_skills = []
    missing_skills = []

    if req_skills:
        for req_s in req_skills:
            norm_req_s = normalize_skill(req_s)
            matched = (
                norm_req_s in candidate_skills_set
                or any(are_skills_semantically_related(norm_req_s, cs) for cs in candidate_skills_set)
            )
            if matched:
                matched_skills.append(req_s)
            else:
                missing_skills.append(req_s)
        match_ratio = len(matched_skills) / len(req_skills)
        required_skills_score = round(match_ratio * 30)
    else:
        # Fallback when JD has no explicit skills extracted
        # Score conservatively based on whether title matches candidate's core stack
        title_lower_check = (requirements.title or "").lower()
        if any(w in title_lower_check for w in ["python", "fastapi", "django", "ai", "machine learning", "llm", "backend"]):
            required_skills_score = 15
        elif any(w in title_lower_check for w in ["software engineer", "software developer", "sde", "developer", "engineer", "full stack", "fullstack"]):
            required_skills_score = 10
        else:
            required_skills_score = 0

    # 4. Preferred Skills Bonus (0–5 pts)
    pref_skills = [s for s in getattr(requirements, "preferred_skills", []) if s.strip()]
    if pref_skills:
        pref_matched = [
            s for s in pref_skills
            if normalize_skill(s) in candidate_skills_set
            or any(are_skills_semantically_related(normalize_skill(s), cs) for cs in candidate_skills_set)
        ]
        preferred_skills_score = round((len(pref_matched) / len(pref_skills)) * 5)
    else:
        preferred_skills_score = 0

    # 5. Experience Depth Fit (0–20 pts) — month-aware datetime calculation
    total_exp_years = _compute_experience_years(candidate)
    min_years = float(requirements.min_years_experience or 0)
    title_lower = (getattr(requirements, "title", "") or "").lower()
    is_early_career = (
        any(w in title_lower for w in ["fresher", "junior", "associate", "entry level", "graduate", "trainee", "intern"])
        or min_years <= 2.0
    )

    if is_early_career or min_years <= 2.0:
        experience_fit_score = 20
    else:
        exp_ratio = min(1.0, total_exp_years / max(min_years, 0.5))
        experience_fit_score = round(exp_ratio * 20)

    # 6. Project Relevance (0–15 pts) — JD keyword overlap
    jd_keywords_set: Set[str] = {normalize_skill(k) for k in requirements.keywords if k.strip()}
    jd_keywords_set.update(normalize_skill(s) for s in req_skills)

    if candidate.projects and jd_keywords_set:
        project_rel_score = 0
        for proj in candidate.projects:
            proj_tech = {normalize_skill(t) for t in proj.technologies}
            overlap = len(proj_tech & jd_keywords_set)
            project_rel_score += min(5, overlap * 2)
        project_relevance_score = min(15, project_rel_score)
    else:
        project_relevance_score = 0

    # 7. Technical Semantic Similarity (0–15 pts) — Hybrid AI Vector & Cluster Matching
    from src.matching.semantic import SemanticMatcher
    cand_summary_text = f"{candidate.summary or ''} {' '.join(candidate.skills[:20])}"
    jd_desc_text = f"{requirements.title or ''} {' '.join(req_skills)} {' '.join(requirements.keywords or [])}"
    vector_sim = SemanticMatcher.compute_semantic_similarity(cand_summary_text, jd_desc_text)

    if jd_keywords_set:
        tech_matched = [
            k for k in jd_keywords_set
            if k in candidate_skills_set
            or any(are_skills_semantically_related(k, cs) for cs in candidate_skills_set)
        ]
        tech_ratio = len(tech_matched) / len(jd_keywords_set)
        blended_ratio = (tech_ratio * 0.65) + (vector_sim * 0.35)
        technical_similarity_score = round(blended_ratio * 15)
    elif vector_sim > 0.35:
        technical_similarity_score = round(vector_sim * 10)
    else:
        technical_similarity_score = 0

    # 8. Education Fit (0–5 pts)
    education_score = 5 if candidate.education else 3

    # 9. Location Fit (0–5 pts) — city alias map
    cand_loc = candidate.contact_info.location or ""
    jd_loc = requirements.location or ""
    location_score = 5 if _location_matches(cand_loc, jd_loc) else 2

    # 10. Other Factors: Title Relevance + Certifications (0–5 pts)
    TARGET_ROLE_KEYWORDS = {
        "ai", "ml", "machine learning", "llm", "nlp", "data scientist", "applied",
        "python", "backend", "software", "data engineer", "full stack", "fullstack",
        "genai", "generative", "rag", "research", "developer", "engineer"
    }
    title_relevance = any(kw in title_lower for kw in TARGET_ROLE_KEYWORDS)
    title_bonus = 3 if title_relevance else 0
    cert_bonus = 2 if candidate.certifications else 1
    other_factors_score = min(5, title_bonus + cert_bonus)

    # 11. Technology & Domain Penalties:
    # If the job title explicitly requires a tech stack the candidate doesn't have (e.g. C++, C#, Ruby, PHP, Swift, iOS)
    TECH_TITLE_KEYWORDS = {
        "c++": ["c++", "cpp"],
        "c#": ["c#", ".net", "dotnet"],
        "golang": ["golang", "go developer", "go engineer"],
        "rust": ["rust developer", "rust engineer"],
        "ruby": ["ruby", "rails"],
        "php": ["php", "laravel", "symfony"],
        "swift": ["swift", "ios developer", "ios engineer"],
        "kotlin": ["kotlin", "android developer", "android engineer"],
        "flutter": ["flutter"],
    }
    title_tech_penalty = 0
    for tech_name, patterns in TECH_TITLE_KEYWORDS.items():
        if any(p in title_lower for p in patterns):
            if not any(are_skills_semantically_related(tech_name, cs) or tech_name in cs for cs in candidate_skills_set):
                title_tech_penalty = 30
                missing_skills.append(f"Title requires {tech_name.upper()} (missing from profile)")
                break

    # Domain mismatch penalty (Infrastructure, Security, Hardware, QA, Network)
    OFF_TARGET_DOMAINS = [
        "security engineer", "infrastructure engineer", "quality engineer", "qa engineer",
        "hardware engineer", "network engineer", "devops engineer", "penetration tester",
        "soc analyst", "cyber security"
    ]
    domain_penalty = 25 if any(dom in title_lower for dom in OFF_TARGET_DOMAINS) else 0

    # Total Score
    total_score = (
        required_skills_score
        + preferred_skills_score
        + experience_fit_score
        + project_relevance_score
        + technical_similarity_score
        + education_score
        + location_score
        + other_factors_score
        - title_tech_penalty
        - domain_penalty
    )
    total_score = min(100, max(0, total_score))

    # Decision mapping
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
        f"Required Skills: {len(matched_skills)}/{len(req_skills) if req_skills else 1} matched. "
        f"Preferred Skills bonus: {preferred_skills_score}/5. "
        f"Experience: ~{total_exp_years}yrs (JD needs {min_years}yrs). "
        f"Missing required: {', '.join(missing_skills) if missing_skills else 'None'}."
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
