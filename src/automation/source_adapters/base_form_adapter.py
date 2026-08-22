from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any
from playwright.sync_api import Page
from src.resume.validator import CandidateProfile
from src.ai.schemas import ApplicationAnswerOutput

class BaseFormAdapter(ABC):
    """Abstract base class for portal-specific form filler adapters."""

    def __init__(self, portal_name: str):
        self.portal_name = portal_name

    @abstractmethod
    def fill_application_form(
        self,
        page: Page,
        profile: CandidateProfile,
        tailored_pdf_path: Path,
        answers: List[ApplicationAnswerOutput]
    ) -> bool:
        """Populates all detected application form fields."""
        pass
