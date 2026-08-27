import pytest
from pathlib import Path
from src.resume.validator import CandidateProfile, ContactInfo
from src.automation.browser import BrowserManager
from src.automation.source_adapters.generic_form_adapter import GenericFormAdapter

def test_dummy_form_filling(tmp_path):
    dummy_html_path = Path(__file__).resolve().parent / "dummy_app.html"
    assert dummy_html_path.exists()
    
    # Create sample PDF resume to upload
    sample_pdf = tmp_path / "sample_tailored.pdf"
    sample_pdf.write_bytes(b"%PDF-1.4 Dummy Resume Content")
    
    profile = CandidateProfile(
        contact_info=ContactInfo(
            full_name="Hemanth Kumar",
            email="hemanth@example.com",
            phone="+1-555-0199",
            location="Seattle, WA",
            linkedin="https://linkedin.com/in/hemanth"
        )
    )
    
    adapter = GenericFormAdapter()
    
    # Run Playwright in headless mode for unit testing
    bm = BrowserManager(headless=True, slow_mo=0, user_data_dir=tmp_path / "browser_data")
    page = bm.start()
    
    try:
        # Navigate to local file URL
        file_url = dummy_html_path.as_uri()
        page.goto(file_url)
        
        success = adapter.fill_application_form(page, profile, sample_pdf, [])
        assert success is True
        
        # Verify filled inputs in DOM
        assert page.locator("#full_name").input_value() == "Hemanth Kumar"
        assert page.locator("#email").input_value() == "hemanth@example.com"
        assert page.locator("#phone").input_value() == "+1-555-0199"
        assert page.locator("#location").input_value() == "Seattle, WA"
        assert page.locator("#linkedin").input_value() == "https://linkedin.com/in/hemanth"
        
        # Verify file input uploaded
        file_val = page.locator("#resume").input_value()
        assert "sample_tailored.pdf" in file_val
        
    finally:
        bm.stop()
