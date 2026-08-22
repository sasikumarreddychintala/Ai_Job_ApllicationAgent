from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class RawJobListing(BaseModel):
    title: str = Field(..., description="Raw job title")
    company: str = Field(..., description="Company name")
    location: Optional[str] = Field("Remote", description="Job location or Remote/Hybrid")
    description: str = Field(..., description="Raw Job Description text")
    url: str = Field(..., description="Source job listing URL")
    source: str = Field(..., description="Source identifier (e.g. greenhouse, lever, custom_fixture)")
    posted_date: Optional[str] = Field(None, description="Job posting date string")

class NormalizedJob(BaseModel):
    fingerprint: str = Field(..., description="Stable SHA-256 fingerprint hash")
    title: str = Field(..., description="Cleaned job title")
    company: str = Field(..., description="Cleaned company name")
    location: str = Field(..., description="Cleaned location")
    description: str = Field(..., description="Normalized raw JD text")
    url: str = Field(..., description="Job URL")
    source: str = Field(..., description="Source identifier")
    discovered_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
