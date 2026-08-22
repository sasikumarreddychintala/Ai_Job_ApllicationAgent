from typing import List, Optional
from pydantic import BaseModel, Field
from src.ai.schemas import ParsedJDRequirements

class JDAnalysisResult(BaseModel):
    job_id: int
    requirements: ParsedJDRequirements
    analyzed_at: str
