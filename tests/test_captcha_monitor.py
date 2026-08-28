import pytest
import sqlite3
from src.database.models import init_db
from src.jobs.schemas import RawJobListing
from src.jobs.finder import JobFinder
from src.jobs.source_adapters.local_fixture_adapter import LocalFixtureAdapter
from src.automation.checkpoint import save_application_checkpoint, load_latest_checkpoint
from src.automation.captcha_monitor import CaptchaMonitor

def test_checkpoint_save_and_load(tmp_path):
    db_file = tmp_path / "test_ckpt.db"
    
    # Insert initial job & application
    finder = JobFinder(adapters=[LocalFixtureAdapter()], db_path=db_file)
    finder.discover_jobs()
    
    # Save checkpoint
    evt_id = save_application_checkpoint(1, "TEST_STEP", {"field": "value"}, db_path=db_file)
    assert evt_id is not None
    
    # Load checkpoint
    ckpt = load_latest_checkpoint(1, db_path=db_file)
    assert ckpt is not None
    assert ckpt["step_name"] == "TEST_STEP"
    assert ckpt["field"] == "value"

def test_captcha_detection():
    monitor = CaptchaMonitor()
    
    class DummyLocator:
        def __init__(self, visible=True):
            self.visible = visible
        def count(self):
            return 1
        @property
        def first(self):
            return self
        def is_visible(self):
            return self.visible
            
    class DummyPage:
        def locator(self, selector):
            if "recaptcha" in selector:
                return DummyLocator(visible=True)
            return DummyLocator(visible=False)
            
    page = DummyPage()
    assert monitor.detect_captcha(page) is True

def test_captcha_pause_and_polling_resume(tmp_path):
    db_file = tmp_path / "test_captcha.db"
    finder = JobFinder(adapters=[LocalFixtureAdapter()], db_path=db_file)
    finder.discover_jobs()
    
    monitor = CaptchaMonitor(db_path=db_file)
    
    # Simulate page where CAPTCHA is visible at t=0, and clears after 1 check
    class MockPage:
        def __init__(self):
            self.checks = 0
            self.url = "https://example.com/apply"
            
        def locator(self, sel):
            class MockLoc:
                def __init__(self, count):
                    self._count = count
                def count(self):
                    return self._count
                @property
                def first(self):
                    return self
                def is_visible(self):
                    return True
            # First check returns CAPTCHA, second check returns cleared (count=0)
            if self.checks == 0:
                return MockLoc(1)
            return MockLoc(0)
            
    page = MockPage()
    
    # Simulate user solving CAPTCHA after poll interval
    def mock_detect(p):
        p.checks += 1
        return p.checks == 1
        
    monitor.detect_captcha = mock_detect
    
    res = monitor.handle_captcha_pause(page, job_id=1, company="TechCorp", title="AI Engineer", max_wait_seconds=10, poll_interval=1)
    assert res is True
    
    # Verify DB checkpoint
    ckpt = load_latest_checkpoint(1, db_path=db_file)
    assert ckpt["step_name"] == "CAPTCHA_CLEARED"
