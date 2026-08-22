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
    assert "Personal AI Job Application Agent" in html

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
