from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator

class ParsedJDRequirements(BaseModel):
    title: Optional[str] = Field("Software Engineer", description="Extracted job title")
    company: Optional[str] = Field("Unknown Company", description="Company name")
    location: Optional[str] = Field("Remote", description="Job location or Remote/Hybrid")
    employment_type: Optional[str] = Field("Full-time", description="Full-time, Part-time, Contract, etc.")
    min_years_experience: Optional[int] = Field(0, description="Minimum required years of experience")
    required_skills: List[str] = Field(default_factory=list, description="Must-have technical & functional skills")
    preferred_skills: List[str] = Field(default_factory=list, description="Nice-to-have skills")
    education_requirement: Optional[str] = Field(None, description="Required degree level (e.g. Bachelor's, Master's)")
    responsibilities: List[str] = Field(default_factory=list, description="Key duties and responsibilities")
    hard_constraints: List[str] = Field(default_factory=list, description="Visa sponsorship, citizenship, security clearance restrictions")
    keywords: List[str] = Field(default_factory=list, description="Important ATS keywords extracted from JD")

    @field_validator("required_skills", "preferred_skills", "responsibilities", "hard_constraints", "keywords", mode="before")
    @classmethod
    def ensure_list(cls, v: Any) -> List[str]:
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()] if "," in v else [v.strip()] if v.strip() else []
        if isinstance(v, list):
            return [str(x).strip() for x in v if str(x).strip()]
        return []

class MatchScoreBreakdown(BaseModel):
    required_skills_score: int = Field(..., ge=0, le=35, description="Required skills overlap (0-35)")
    experience_fit_score: int = Field(..., ge=0, le=20, description="Experience depth fit (0-20)")
    project_relevance_score: int = Field(..., ge=0, le=15, description="Project alignment (0-15)")
    technical_similarity_score: int = Field(..., ge=0, le=15, description="Semantic tech similarity (0-15)")
    education_score: int = Field(..., ge=0, le=5, description="Education fit (0-5)")
    location_score: int = Field(..., ge=0, le=5, description="Location / remote fit (0-5)")
    other_factors_score: int = Field(..., ge=0, le=5, description="Other factors (0-5)")

class MatchEvaluation(BaseModel):
    overall_score: int = Field(..., ge=0, le=100, description="Total weighted score out of 100")
    decision: str = Field(..., description="SKIP, APPLY, HIGH, or VERY_HIGH")
    score_breakdown: MatchScoreBreakdown
    matched_skills: List[str] = Field(default_factory=list, description="Skills present in both candidate profile & JD")
    missing_required_skills: List[str] = Field(default_factory=list, description="Required skills candidate lacks")
    hard_constraint_violated: bool = Field(False, description="True if visa/clearance/citizenship hard rule failed")
    reasoning: str = Field(..., description="Detailed transparent justification for the decision")

class TailoredBulletPoint(BaseModel):
    original: str = Field(..., description="Original bullet point from candidate master resume")
    tailored: str = Field(..., description="Rephrased bullet point highlighting relevant keywords without altering facts")
    keywords_added: List[str] = Field(default_factory=list, description="ATS keywords naturally integrated")

class TailoredProject(BaseModel):
    name: str = Field(..., description="Project name")
    technologies: List[str] = Field(default_factory=list, description="Targeted tech stack for project")
    description: str = Field(..., description="Tailored impact description highlighting JD relevant keywords")

class TailoredResumeOutput(BaseModel):
    summary: str = Field(..., description="Truthful targeted professional summary aligned with JD")
    highlighted_skills: List[str] = Field(default_factory=list, description="Skills prioritized for this specific job")
    revised_bullet_points: List[TailoredBulletPoint] = Field(default_factory=list, description="Truthfully tailored experience bullets")
    tailored_projects: List[TailoredProject] = Field(default_factory=list, description="Tailored projects highlighting JD keywords")
    tailored_period: Optional[str] = Field(None, description="Job-specific tailored experience period (e.g. Jul 2024 - Present)")
    shortlist_score: int = Field(95, description="Optimized ATS match score after tailoring (e.g. 95-98%)")
    truth_verified: bool = Field(True, description="Confirmation that no facts, dates, or titles were fabricated")

class ApplicationAnswerOutput(BaseModel):
    question: str = Field(..., description="The application question being answered")
    answer: str = Field(..., description="Generated truthful answer based strictly on verified profile facts")
    is_known: bool = Field(True, description="True if answer is based on verified facts, False if information is unknown")
    requires_manual_review: bool = Field(False, description="True if answer involves legal/unknown declarations requiring human review")
