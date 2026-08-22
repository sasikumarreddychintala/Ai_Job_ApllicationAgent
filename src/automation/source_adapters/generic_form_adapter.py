from pathlib import Path
from typing import List
from playwright.sync_api import Page
from src.resume.validator import CandidateProfile
from src.ai.schemas import ApplicationAnswerOutput
from src.automation.form_filler import FormFiller
from src.automation.source_adapters.base_form_adapter import BaseFormAdapter
from src.utils.logger import logger

class GenericFormAdapter(BaseFormAdapter):
    """Generic heuristic form adapter for standard ATS web application forms."""

    def __init__(self):
        super().__init__(portal_name="generic_ats")

    def fill_application_form(
        self,
        page: Page,
        profile: CandidateProfile,
        tailored_pdf_path: Path,
        answers: List[ApplicationAnswerOutput]
    ) -> bool:
        filler = FormFiller(page)
        c = profile.contact_info

        logger.info(f" Filling application form for {c.full_name} via GenericFormAdapter...")

        # 0. Check if page has an "Apply", "Apply Now", or "Easy Apply" button to open the form
        try:
            apply_buttons = [
                "a:has-text('Apply Now')",
                "button:has-text('Apply Now')",
                "a:has-text('Easy Apply')",
                "button:has-text('Easy Apply')",
                "a:has-text('Apply on company website')",
                "button:has-text('Apply on company website')",
                "button.jobs-apply-button",
                "a[href*='apply']"
            ]
            for btn_sel in apply_buttons:
                btn = page.locator(btn_sel).first
                if btn.count() > 0 and btn.is_visible():
                    logger.info(f" Found application button '{btn_sel}'. Clicking to open form...")
                    try:
                        btn.click(timeout=3000)
                        page.wait_for_timeout(2000)
                        break
                    except Exception:
                        pass
        except Exception:
            pass

        # 1. Contact Information
        filler.fill_text_field("name", c.full_name)
        filler.fill_text_field("full_name", c.full_name)
        filler.fill_text_field("first_name", c.full_name.split()[0])
        if len(c.full_name.split()) > 1:
            filler.fill_text_field("last_name", " ".join(c.full_name.split()[1:]))

        filler.fill_text_field("email", c.email)
        if c.phone:
            filler.fill_text_field("phone", c.phone)
            filler.fill_text_field("mobile", c.phone)
        if c.location:
            filler.fill_text_field("location", c.location)
            filler.fill_text_field("city", c.location)
        if c.linkedin:
            filler.fill_text_field("linkedin", c.linkedin)
        if c.github:
            filler.fill_text_field("github", c.github)
        if c.portfolio:
            filler.fill_text_field("portfolio", c.portfolio)
            filler.fill_text_field("website", c.portfolio)

        # 2. Upload Resume PDF
        if tailored_pdf_path and tailored_pdf_path.exists():
            filler.upload_file("resume", tailored_pdf_path)

        # 3. Answer Custom Application Questions
        for ans in answers:
            if ans.is_known and ans.answer and not ans.requires_manual_review:
                filler.fill_text_field(ans.question, ans.answer)

        logger.info(" Form population completed successfully.")
        return True

