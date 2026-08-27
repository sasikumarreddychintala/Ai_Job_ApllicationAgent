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

    import re
    # Calculate candidate's total experience years
    candidate_exp_years = 0.0
    for exp in candidate.experience:
        start_str = str(exp.start_date or "").strip().lower()
        end_str = str(exp.end_date or "present").strip().lower()
        start_years = re.findall(r'\b(20\d\d|19\d\d)\b', start_str)
        end_years = re.findall(r'\b(20\d\d|19\d\d)\b', end_str)
        if start_years and end_years:
            diff = int(end_years[0]) - int(start_years[0])
            candidate_exp_years += max(1.0, float(diff))
        elif start_years:
            candidate_exp_years += max(1.0, 2026 - int(start_years[0]))
        else:
            candidate_exp_years += 1.0

    is_early_career_candidate = candidate_exp_years <= 2.5
    req_exp = float(requirements.min_years_experience or 0)

    if is_early_career_candidate and req_exp > 2.0:
        reason = f"Experience constraint failed: Job requires {requirements.min_years_experience}+ years. Candidate profile is strictly 0-2 Yrs / Early Career."
        logger.info(f"[SKIP] Skipping high experience role requiring {requirements.min_years_experience}+ yrs.")
        return True, reason
    elif not is_early_career_candidate and req_exp > (candidate_exp_years + 1.5):
        reason = f"Experience constraint failed: Job requires {requirements.min_years_experience}+ years. Candidate has ~{round(candidate_exp_years)} years."
        logger.info(f"[SKIP] Skipping high experience role requiring {requirements.min_years_experience}+ yrs.")
        return True, reason

    # Hard Constraints from Job Requirements (Citizenship, Clearance, Sponsorship)
    for hc in getattr(requirements, "hard_constraints", []):
        hc_lower = hc.lower()
        if "citizen" in hc_lower or "citizenship" in hc_lower or "clearance" in hc_lower:
            if "citizen" not in work_auth and "authorized" not in work_auth:
                reason = f"Hard constraint failed: Job requires '{hc}'."
                logger.info(f"[SKIP] {reason}")
                return True, reason
        if "no sponsor" in hc_lower or "sponsorship not available" in hc_lower:
            if "requires sponsorship" in work_auth or "h1b" in work_auth:
                reason = f"Hard constraint failed: Job does not sponsor visas ('{hc}')."
                logger.info(f"[SKIP] {reason}")
                return True, reason

    return False, None
