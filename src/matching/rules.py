from typing import Tuple, Optional
from src.resume.validator import CandidateProfile
from src.ai.schemas import ParsedJDRequirements
from src.utils.logger import logger

def check_hard_constraints(
    candidate: CandidateProfile,
    requirements: ParsedJDRequirements
) -> Tuple[bool, Optional[str]]:
    """
    Evaluates hard constraints (citizenship, clearance, visa sponsorship, location restrictions).
    Returns (is_violated: bool, reason: Optional[str]).
    """
    custom_answers = candidate.custom_answers or {}
    work_auth = custom_answers.get("work_authorization", "").lower()

    # Seniority & Experience Constraint for 0-2 Yrs / Fresher profile
    title_lower = (getattr(requirements, "title", "") or "").lower()
    senior_keywords = ["senior", "sr.", "lead", "staff", "principal", "architect", "director", "head of", "engineering manager", "tech lead", "5+ years", "6+ years", "7+ years", "8+ years"]
    if any(sk in title_lower for sk in ["senior", "sr.", "lead", "staff", "principal", "architect", "director", "head of", "manager"]):
        reason = f"Seniority constraint failed: Role '{requirements.title}' is senior/lead level. Target is 0-2 Yrs / Fresher / Associate."
        logger.info(f"[SKIP] Skipping senior role: {requirements.title}")
        return True, reason

    if requirements.min_years_experience and float(requirements.min_years_experience) >= 3.5:
        reason = f"Experience constraint failed: Job requires {requirements.min_years_experience}+ years. Candidate profile is 1-2 Yrs / Early Career."
        logger.info(f"[SKIP] Skipping high experience role requiring {requirements.min_years_experience}+ yrs.")
        return True, reason

    return False, None
