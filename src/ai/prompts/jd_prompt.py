"""
Prompt Version: 1.0
Target Task: Parse Job Description (JD) into ParsedJDRequirements schema.
Safety Rules: Extract strictly from provided text. Do not invent requirements.
"""

JD_ANALYSIS_PROMPT_V1 = """
You are an expert technical recruiter and job analyst AI.
Analyze the following Job Description (JD) text and extract structured information strictly according to the JSON schema below.

JSON Schema format:
{
  "title": "<Job Title>",
  "company": "<Company Name>",
  "location": "<Location or Remote/Hybrid>",
  "employment_type": "<Full-time/Part-time/Contract>",
  "min_years_experience": 3,
  "required_skills": ["Skill1", "Skill2"],
  "preferred_skills": ["SkillA", "SkillB"],
  "education_requirement": "<Required degree or null>",
  "responsibilities": ["Duty 1", "Duty 2"],
  "hard_constraints": ["US Citizenship Required", "Must pass Security Clearance"],
  "keywords": ["Keyword1", "Keyword2"]
}

Rules:
1. Output ONLY valid JSON matching the schema.
2. If a field is not specified in the JD, set it to null or an empty list.
3. Identify strict hard constraints (e.g. visa, citizenship, security clearance, location requirements).

JOB DESCRIPTION TEXT:
{jd_text}
"""

def render_jd_prompt(jd_text: str) -> str:
    # Cap JD text at 3500 chars to avoid model timeouts while preserving core requirements
    clean_text = jd_text[:3500] if len(jd_text) > 3500 else jd_text
    return JD_ANALYSIS_PROMPT_V1.replace("{jd_text}", clean_text)
