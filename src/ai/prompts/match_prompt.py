"""
Prompt Version: 1.0
Target Task: Evaluate match between verified candidate profile and structured JD requirements.
Safety Rules: Objective scoring based strictly on facts. Never increase score by guessing or inventing candidate skills.
"""

MATCH_EVALUATION_PROMPT_V1 = """
You are an objective AI job matching evaluator.
Evaluate the fit between the candidate's verified profile and the job requirements.

Weighting Rules:
- Required Skills (0-35 points)
- Experience Fit (0-20 points)
- Project Relevance (0-15 points)
- Technical Similarity (0-15 points)
- Education (0-5 points)
- Location Fit (0-5 points)
- Other Factors (0-5 points)

Total overall_score = sum of above breakdown scores (0 to 100).

Decision thresholds:
- overall_score < 70: "SKIP"
- 70 <= overall_score <= 79: "APPLY"
- 80 <= overall_score <= 89: "HIGH"
- 90 <= overall_score: "VERY_HIGH"

Hard Constraint Rule:
If the candidate fails any hard constraint (e.g. visa sponsorship required when job says 'No Sponsorship'), set hard_constraint_violated=true and decision="SKIP".

JSON Schema format:
{
  "overall_score": 85,
  "decision": "HIGH",
  "score_breakdown": {
    "required_skills_score": 30,
    "experience_fit_score": 18,
    "project_relevance_score": 12,
    "technical_similarity_score": 12,
    "education_score": 5,
    "location_score": 4,
    "other_factors_score": 4
  },
  "matched_skills": ["Skill1", "Skill2"],
  "missing_required_skills": ["MissingSkill1"],
  "hard_constraint_violated": false,
  "reasoning": "Clear justification for score breakdown."
}

CANDIDATE PROFILE JSON:
{profile_json}

JOB REQUIREMENTS JSON:
{requirements_json}
"""

def render_match_prompt(profile_json: str, requirements_json: str) -> str:
    prompt = MATCH_EVALUATION_PROMPT_V1.replace("{profile_json}", profile_json)
    return prompt.replace("{requirements_json}", requirements_json)
