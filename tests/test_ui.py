import json
import threading
import urllib.request
import pytest
from http.server import HTTPServer
from src.ui.app import AgentDashboardHandler, DASHBOARD_HTML

@pytest.fixture(scope="module")
def local_server():
    server = HTTPServer(("127.0.0.1", 8999), AgentDashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:8999"
    server.shutdown()
    server.server_close()

def test_dashboard_html_response(local_server):
    req = urllib.request.urlopen(f"{local_server}/")
    assert req.status == 200
    html = req.read().decode("utf-8")
    assert "Elevora AI" in html

def test_api_applications_response(local_server):
    req = urllib.request.urlopen(f"{local_server}/api/applications")
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert isinstance(data, list)

def test_api_profile_response(local_server):
    req = urllib.request.urlopen(f"{local_server}/api/profile")
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert isinstance(data, dict)

def test_api_jobs_response(local_server):
    req = urllib.request.urlopen(f"{local_server}/api/jobs")
    assert req.status == 200
    data = json.loads(req.read().decode("utf-8"))
    assert isinstance(data, list)

def test_api_clear_response(local_server):
    post_req = urllib.request.Request(f"{local_server}/api/clear", data=b"{}", method="POST")
    resp = urllib.request.urlopen(post_req)
    assert resp.status == 200
    data = json.loads(resp.read().decode("utf-8"))
    assert data.get("status") == "CLEARED"

def test_api_view_resume_fallback(local_server):
    # Tests that /api/view-resume serves master resume fallback rather than crashing
    try:
        req = urllib.request.urlopen(f"{local_server}/api/view-resume?file=nonexistent.pdf")
        assert req.status in (200, 404)
    except urllib.error.HTTPError as e:
        assert e.code == 404


