import json
import pytest
from unittest.mock import patch, MagicMock
from src.jobs.source_adapters.greenhouse_adapter import GreenhouseJobAdapter
from src.jobs.source_adapters.lever_adapter import LeverJobAdapter
from src.jobs.source_adapters.remoteok_adapter import RemoteOKJobAdapter
from src.jobs.finder import JobFinder

def test_greenhouse_adapter_parsing_and_filter():
    adapter = GreenhouseJobAdapter(company="testcomp")
    sample_response = {
        "jobs": [
            {
                "title": "Senior Python Engineer",
                "location": {"name": "Remote, US"},
                "absolute_url": "https://boards.greenhouse.io/testcomp/jobs/101",
                "content": "<p>Python backend role</p>",
                "updated_at": "2026-08-01"
            },
            {
                "title": "React Frontend Engineer",
                "location": {"name": "New York, NY"},
                "absolute_url": "https://boards.greenhouse.io/testcomp/jobs/102",
                "content": "<p>React role</p>",
                "updated_at": "2026-08-02"
            }
        ]
    }
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(sample_response).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        
        # Test query filter
        jobs = adapter.fetch_jobs(query="Python", location="Remote")
        assert len(jobs) == 1
        assert jobs[0].title == "Senior Python Engineer"
        assert jobs[0].source == "greenhouse"

def test_lever_adapter_parsing_and_filter():
    adapter = LeverJobAdapter(company="testlever")
    sample_response = [
        {
            "text": "Machine Learning Engineer",
            "categories": {"location": "Remote"},
            "hostedUrl": "https://jobs.lever.co/testlever/201",
            "descriptionPlain": "Build LLM systems",
            "createdAt": 1723000000
        }
    ]
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(sample_response).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        
        jobs = adapter.fetch_jobs(query="Machine Learning")
        assert len(jobs) == 1
        assert jobs[0].title == "Machine Learning Engineer"
        assert jobs[0].company == "Testlever"

def test_remoteok_adapter_parsing_and_filter():
    adapter = RemoteOKJobAdapter()
    sample_response = [
        {"legal": "Notice"},
        {
            "position": "Full Stack Python Developer",
            "company": "Remote Solutions",
            "location": "Worldwide",
            "url": "https://remoteok.com/l/301",
            "description": "Full stack Python and React role",
            "tags": ["python", "react", "remote"],
            "date": "2026-08-01"
        }
    ]
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(sample_response).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        
        jobs = adapter.fetch_jobs(query="Python")
        assert len(jobs) == 1
        assert jobs[0].title == "Full Stack Python Developer"
        assert jobs[0].source == "remoteok"

def test_multi_source_finder_creation(tmp_path):
    db_file = tmp_path / "test_multi.db"
    finder = JobFinder.create_multi_source_finder(
        greenhouse_companies=["test1"],
        lever_companies=["test2"],
        db_path=db_file
    )
    assert len(finder.adapters) >= 4
