import json
import csv
import pytest
from pathlib import Path
from src.database.models import init_db
from src.database.audit import AuditManager
from src.jobs.finder import JobFinder
from src.jobs.source_adapters.local_fixture_adapter import LocalFixtureAdapter
from src.automation.checkpoint import save_application_checkpoint

def test_audit_manager_history_and_events(tmp_path):
    db_file = tmp_path / "test_audit.db"
    
    # 1. Populate DB with jobs
    finder = JobFinder(adapters=[LocalFixtureAdapter()], db_path=db_file)
    finder.discover_jobs()
    
    # 2. Record some events
    conn = init_db(db_file)
    save_application_checkpoint(1, "TEST_DISCOVERY", {"source": "local_fixture"}, conn=conn)
    save_application_checkpoint(1, "FORM_FILLED", {"url": "https://example.com"}, conn=conn)
    conn.close()
    
    audit = AuditManager(db_path=db_file)
    history = audit.get_application_history()
    assert len(history) == 2
    assert history[0]["status"] == "DISCOVERED"
    
    events = audit.get_application_events(1)
    assert len(events) == 2
    assert events[0]["event_type"] == "TEST_DISCOVERY"
    assert events[1]["event_type"] == "FORM_FILLED"

def test_audit_manager_export_json_and_csv(tmp_path):
    db_file = tmp_path / "test_audit_export.db"
    json_export = tmp_path / "audit.json"
    csv_export = tmp_path / "audit.csv"
    
    finder = JobFinder(adapters=[LocalFixtureAdapter()], db_path=db_file)
    finder.discover_jobs()
    
    conn = init_db(db_file)
    save_application_checkpoint(1, "SUBMISSION_ATTEMPT", {"status": "SUCCESS"}, conn=conn)
    conn.close()
    
    audit = AuditManager(db_path=db_file)
    
    # Export to JSON
    json_path = audit.export_audit_log_to_json(json_export)
    assert json_path.exists()
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        assert len(data) == 2
        assert "events" in data[0]
        
    # Export to CSV
    csv_path = audit.export_audit_log_to_csv(csv_export)
    assert csv_path.exists()
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["job_id"] in ["1", "2"]
