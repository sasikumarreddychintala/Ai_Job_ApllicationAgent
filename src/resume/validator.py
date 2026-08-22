import re
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, EmailStr

class ContactInfo(BaseModel):
    full_name: str = Field(..., description="Full legal or professional name")
    email: str = Field(..., description="Primary email address")
    phone: Optional[str] = Field(None, description="Phone number")
    location: Optional[str] = Field(None, description="City, State, Country")
    linkedin: Optional[str] = Field(None, description="LinkedIn profile URL")
    github: Optional[str] = Field(None, description="GitHub profile URL")
    portfolio: Optional[str] = Field(None, description="Personal website/portfolio URL")

class WorkExperience(BaseModel):
    company: str = Field(..., description="Employer / Company name")
    position: str = Field(..., description="Job title / Role")
    location: Optional[str] = Field(None, description="Job location or Remote")
    start_date: Optional[str] = Field(None, description="Start date (e.g. MMM YYYY or YYYY)")
    end_date: Optional[str] = Field(None, description="End date (e.g. MMM YYYY, YYYY, or Present)")
    is_current: bool = Field(False, description="Whether this is the candidate's current position")
    highlights: List[str] = Field(default_factory=list, description="Verified achievement bullet points")
    verified_skills: List[str] = Field(default_factory=list, description="Specific technical/functional skills demonstrated")

class Education(BaseModel):
    institution: str = Field(..., description="University / School name")
    degree: str = Field(..., description="Degree obtained (e.g., Bachelor of Science)")
    field_of_study: Optional[str] = Field(None, description="Major / Field of study")
    graduation_year: Optional[str] = Field(None, description="Graduation year or date")
    gpa: Optional[str] = Field(None, description="GPA if applicable")

class Project(BaseModel):
    name: str = Field(..., description="Project name")
    description: str = Field(..., description="Brief description of the project and achievements")
    technologies: List[str] = Field(default_factory=list, description="Technologies / tools used")
    link: Optional[str] = Field(None, description="URL to project repository or live site")

class Certification(BaseModel):
    name: str = Field(..., description="Certification title")
    issuer: Optional[str] = Field(None, description="Issuing organization")
    date: Optional[str] = Field(None, description="Issue date")
    expiry: Optional[str] = Field(None, description="Expiration date if applicable")

class CandidateProfile(BaseModel):
    contact_info: ContactInfo
    summary: Optional[str] = Field(None, description="Professional bio or summary")
    skills: List[str] = Field(default_factory=list, description="Categorized technical & soft skills")
    experience: List[WorkExperience] = Field(default_factory=list, description="Work history listed reverse-chronologically")
    education: List[Education] = Field(default_factory=list, description="Educational background")
    projects: List[Project] = Field(default_factory=list, description="Notable projects")
    certifications: List[Certification] = Field(default_factory=list, description="Certifications and licenses")
    custom_answers: Dict[str, str] = Field(
        default_factory=dict,
        description="User-approved pre-filled application answers (e.g., work authorization, notice period)"
    )

# --- Sensitive Credential & Secret Sanitization ---
SENSITIVE_PATTERNS = [
    (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),  # US SSN
    (r"(?i)\b(sk-[a-zA-Z0-9]{20,})\b", "[REDACTED_API_KEY]"),  # Generic Secret Key
    (r"(?i)\b(password|passwd|secret)\s*[:=]\s*\S+", "[REDACTED_CREDENTIAL]"),
    (r"\b(bearer\s+[a-zA-Z0-9\-\._~\+\/]+=*)\b", "[REDACTED_TOKEN]"),
]

def sanitize_sensitive_data(text: str) -> str:
    """Scrubs sensitive credentials, SSNs, API tokens, and passwords from text."""
    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized
