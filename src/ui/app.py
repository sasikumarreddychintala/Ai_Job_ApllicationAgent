import json
import logging
import queue
import socketserver
import threading
import time
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional

from config import settings
from src.utils.logger import logger
from src.resume.profile import ProfileManager
from src.database.audit import AuditManager
from src.jobs.finder import JobFinder
from src.agents.jd_agent import JDAgent
from src.agents.match_agent import MatchAgent
from src.agents.resume_agent import ResumeTailorAgent
from src.agents.orchestrator import ApplicationOrchestrator
import re
from src.ai.schemas import ParsedJDRequirements
from src.database.models import init_db

# --- Live Activity Log Stream (SSE) ---
# Thread-safe queue holding recent log lines for the UI live feed
_log_queue: queue.Queue = queue.Queue(maxsize=500)
_sse_clients: list = []
_sse_lock = threading.Lock()

class _UILogHandler(logging.Handler):
    """Captures log records and pushes them to SSE clients in real time."""
    LEVEL_COLORS = {
        "INFO": "#38bdf8",
        "WARNING": "#eab308",
        "ERROR": "#ef4444",
        "DEBUG": "#94a3b8",
    }
    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            color = self.LEVEL_COLORS.get(record.levelname, "#f8fafc")
            payload = json.dumps({"level": record.levelname, "msg": msg, "color": color})
            line = f"data: {payload}\n\n"
            with _sse_lock:
                dead = []
                for client_q in _sse_clients:
                    try:
                        client_q.put_nowait(line)
                    except queue.Full:
                        dead.append(client_q)
                for d in dead:
                    _sse_clients.remove(d)
        except Exception:
            pass

# Attach handler to root logger so all agent logs are captured
_ui_handler = _UILogHandler()
_ui_handler.setFormatter(logging.Formatter("%(message)s"))
_ui_handler.setLevel(logging.INFO)
logging.getLogger().addHandler(_ui_handler)


FAVICON_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <defs>
    <linearGradient id="g1" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
      <stop stop-color="#38bdf8"/>
      <stop offset="0.5" stop-color="#818cf8"/>
      <stop offset="1" stop-color="#c084fc"/>
    </linearGradient>
    <linearGradient id="bg1" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
      <stop stop-color="#0f172a"/>
      <stop offset="1" stop-color="#020617"/>
    </linearGradient>
    <filter id="glow1" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur stdDeviation="2.5" result="b"/>
      <feComposite in="SourceGraphic" in2="b" operator="over"/>
    </filter>
  </defs>
  <rect width="64" height="64" rx="16" fill="url(#bg1)" stroke="url(#g1)" stroke-width="2.5"/>
  <path d="M22 23V17C22 14.7909 23.7909 13 26 13H38C40.2091 13 42 14.7909 42 17V23" stroke="url(#g1)" stroke-width="3" stroke-linecap="round"/>
  <rect x="13" y="23" width="38" height="27" rx="7" fill="#131f37" stroke="url(#g1)" stroke-width="2.5"/>
  <path d="M13 33.5C23.5 39 40.5 39 51 33.5" stroke="url(#g1)" stroke-width="2" stroke-linecap="round"/>
  <circle cx="32" cy="34" r="4" fill="#38bdf8" filter="url(#glow1)"/>
  <path d="M49 10L50.5 14L54.5 15.5L50.5 17L49 21L47.5 17L43.5 15.5L47.5 14L49 10Z" fill="#38bdf8"/>
</svg>"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Elevora AI | Autonomous Job Application Agent</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.ico">
    <style>
        :root {
            --bg-color: #070d1e;
            --card-bg: rgba(19, 31, 55, 0.85);
            --card-border: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --accent-glow: rgba(56, 189, 248, 0.25);
            --purple: #a855f7;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
        }
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Inter, Helvetica, sans-serif;
            background: radial-gradient(circle at 50% 0%, #0d1e3d 0%, #070d1e 100%);
            color: var(--text-main);
            margin: 0;
            padding: 20px 24px 60px;
            min-height: 100vh;
        }
        /* Top Navigation & Brand Header */
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(30, 41, 59, 0.8);
            padding-bottom: 16px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 16px;
        }
        .brand-container {
            display: flex;
            align-items: center;
            gap: 14px;
        }
        .brand-logo {
            width: 44px;
            height: 44px;
            border-radius: 12px;
            background: linear-gradient(135deg, #0ea5e9, #6366f1, #a855f7);
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 0 16px rgba(56, 189, 248, 0.35);
            flex-shrink: 0;
        }
        .brand-logo svg { width: 28px; height: 28px; }
        .brand-title {
            margin: 0;
            font-size: 21px;
            font-weight: 800;
            letter-spacing: -0.02em;
            background: linear-gradient(135deg, #ffffff 30%, #7dd3fc 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .brand-subtitle {
            margin: 2px 0 0 0;
            color: var(--text-muted);
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .live-tag {
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }
        .live-tag::before {
            content: '';
            width: 6px;
            height: 6px;
            background: #10b981;
            border-radius: 50%;
            display: inline-block;
            box-shadow: 0 0 6px #10b981;
            animation: pulse-dot 1.5s infinite;
        }
        @keyframes pulse-dot { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.8); } }

        /* Stats Grid */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 14px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 16px 18px;
            backdrop-filter: blur(10px);
            transition: transform 0.2s, border-color 0.2s;
            position: relative;
            overflow: hidden;
        }
        .stat-card:hover {
            transform: translateY(-2px);
            border-color: rgba(56, 189, 248, 0.4);
        }
        .stat-label { font-size: 12px; color: var(--text-muted); text-transform: uppercase; font-weight: 600; letter-spacing: 0.04em; }
        .stat-val { font-size: 26px; font-weight: 800; margin-top: 4px; }

        /* Glass Cards */
        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 20px;
            margin-bottom: 20px;
            backdrop-filter: blur(12px);
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
        }

        /* Buttons & Inputs */
        .btn {
            background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%);
            color: #ffffff;
            font-weight: 600;
            border: 1px solid rgba(56, 189, 248, 0.3);
            padding: 9px 16px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
            box-shadow: 0 2px 8px rgba(2, 132, 199, 0.25);
        }
        .btn:hover { opacity: 0.95; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(2, 132, 199, 0.4); }
        .btn:active { transform: translateY(0); }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }
        
        .btn-green {
            background: linear-gradient(135deg, #059669 0%, #047857 100%);
            border-color: rgba(52, 211, 153, 0.3);
            box-shadow: 0 2px 8px rgba(5, 150, 105, 0.25);
        }
        .btn-green:hover { box-shadow: 0 4px 12px rgba(5, 150, 105, 0.4); }

        .btn-purple {
            background: linear-gradient(135deg, #7c3aed 0%, #6d28d9 100%);
            border-color: rgba(192, 132, 252, 0.3);
            box-shadow: 0 2px 8px rgba(124, 58, 237, 0.25);
        }

        .btn-outline {
            background: rgba(15, 23, 42, 0.6);
            color: #cbd5e1;
            border: 1px solid #334155;
            box-shadow: none;
        }
        .btn-outline:hover {
            background: rgba(30, 41, 59, 0.8);
            color: #ffffff;
            border-color: #64748b;
        }

        .input-box {
            background: #090e1c;
            border: 1px solid #1e293b;
            color: #f8fafc;
            padding: 9px 13px;
            border-radius: 8px;
            font-size: 13px;
            outline: none;
            transition: border-color 0.2s;
        }
        .input-box:focus { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.15); }

        /* Search Container */
        .search-bar {
            display: flex;
            gap: 10px;
            margin-top: 12px;
            flex-wrap: wrap;
        }

        /* View Mode Navigation Tabs */
        .view-tabs {
            display: flex;
            align-items: center;
            gap: 8px;
            border-bottom: 1px solid #1e293b;
            padding-bottom: 12px;
            margin-bottom: 16px;
            flex-wrap: wrap;
        }
        .v-tab-btn {
            background: transparent;
            border: 1px solid transparent;
            color: var(--text-muted);
            font-size: 13px;
            font-weight: 600;
            padding: 8px 14px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .v-tab-btn:hover { color: #f8fafc; background: rgba(255, 255, 255, 0.04); }
        .v-tab-btn.active {
            background: rgba(56, 189, 248, 0.12);
            color: #38bdf8;
            border-color: rgba(56, 189, 248, 0.3);
        }
        .v-tab-btn .tab-count {
            background: rgba(255, 255, 255, 0.1);
            color: inherit;
            padding: 2px 7px;
            border-radius: 999px;
            font-size: 11px;
            font-weight: 700;
        }
        .v-tab-btn.active .tab-count {
            background: rgba(56, 189, 248, 0.25);
            color: #7dd3fc;
        }

        /* Table & Row Animations */
        table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin-top: 8px;
        }
        th, td {
            text-align: left;
            padding: 12px 14px;
            font-size: 13px;
            border-bottom: 1px solid #1e293b;
        }
        th {
            color: var(--text-muted);
            font-size: 11px;
            text-transform: uppercase;
            font-weight: 700;
            letter-spacing: 0.05em;
            background: rgba(11, 19, 41, 0.5);
            position: sticky;
            top: 0;
            z-index: 10;
        }
        tbody tr {
            transition: background 0.15s ease;
        }
        tbody tr:hover {
            background: rgba(30, 41, 59, 0.4);
        }

        /* One-by-One Real-time Row Entrance Animation */
        @keyframes rowSlideIn {
            0% {
                opacity: 0;
                transform: translateY(-10px) scale(0.99);
                background: rgba(56, 189, 248, 0.25);
            }
            100% {
                opacity: 1;
                transform: translateY(0) scale(1);
                background: transparent;
            }
        }
        .row-stream-new {
            animation: rowSlideIn 0.4s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }

        .badge {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.02em;
        }
        .badge-DISCOVERED { background: rgba(148, 163, 184, 0.15); color: #cbd5e1; border: 1px solid rgba(148, 163, 184, 0.3); }
        .badge-ANALYZED { background: rgba(168, 85, 247, 0.15); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3); }
        .badge-QUALIFIED { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); }
        .badge-RESUME_READY { background: rgba(245, 158, 11, 0.15); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.35); }
        .badge-READY_TO_SUBMIT { background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); }
        .badge-SUBMITTED { background: rgba(16, 185, 129, 0.3); color: #a7f3d0; border: 1px solid #10b981; }
        .badge-SKIPPED { background: rgba(239, 68, 68, 0.15); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.25); }

        .score-high { color: #34d399; font-weight: 800; font-size: 14px; text-shadow: 0 0 8px rgba(52, 211, 153, 0.3); }
        .score-med { color: #fbbf24; font-weight: 700; }
        .score-low { color: #94a3b8; }

        /* Scanning Radar Banner */
        .radar-box {
            display: none;
            background: linear-gradient(90deg, rgba(14, 165, 233, 0.15), rgba(99, 102, 241, 0.15));
            border: 1px solid rgba(56, 189, 248, 0.3);
            border-radius: 10px;
            padding: 12px 16px;
            margin-bottom: 14px;
            align-items: center;
            justify-content: space-between;
            gap: 12px;
        }
        .radar-box.active { display: flex; }
        .radar-dot {
            width: 10px; height: 10px;
            border-radius: 50%;
            background: #38bdf8;
            box-shadow: 0 0 10px #38bdf8;
            animation: pulse-dot 1s infinite alternate;
        }

        /* Live Activity Terminal */
        .log-panel {
            background: #050914;
            border: 1px solid #1e293b;
            border-radius: 10px;
            padding: 12px 14px;
            margin-bottom: 20px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 12px;
            min-height: 110px;
            max-height: 180px;
            overflow-y: auto;
            scroll-behavior: smooth;
        }
        .log-panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .log-line { padding: 2px 0; line-height: 1.5; word-break: break-word; }

        /* Modals */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(6px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-overlay.open { display: flex; }
        .modal-box {
            background: #0b1426;
            border: 1px solid #334155;
            border-radius: 14px;
            width: 90%;
            max-width: 680px;
            max-height: 85vh;
            overflow-y: auto;
            padding: 24px;
            box-shadow: 0 24px 48px rgba(0,0,0,0.6);
            position: relative;
        }
        .modal-tabs {
            display: flex;
            gap: 8px;
            margin: 16px 0;
            border-bottom: 1px solid #1e293b;
            padding-bottom: 8px;
            overflow-x: auto;
        }
        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 12px;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
        }
        .tab-btn.active {
            background: rgba(56, 189, 248, 0.15);
            color: var(--accent);
        }
        .outreach-content-box {
            background: #050914;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 14px;
            font-size: 13px;
            line-height: 1.6;
            color: #cbd5e1;
            white-space: pre-wrap;
            margin-bottom: 12px;
            min-height: 120px;
        }
        .toast {
            display: none;
            position: fixed;
            bottom: 24px;
            right: 24px;
            background: #10b981;
            color: #fff;
            padding: 10px 18px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 13px;
            box-shadow: 0 6px 18px rgba(0,0,0,0.4);
            z-index: 2000;
        }
    </style>
</head>
<body>
    <!-- Toast -->
    <div id="copy-toast" class="toast">✅ Action complete!</div>

    <!-- Outreach Modal -->
    <div id="outreach-modal" class="modal-overlay" onclick="if(event.target===this) closeOutreachModal()">
        <div class="modal-box">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <h2 id="modal-company-title" style="margin: 0; font-size: 18px; color: var(--accent);">Recruiter Outreach & Prep</h2>
                    <p id="modal-role-subtitle" style="margin: 4px 0 0 0; color: var(--text-muted); font-size: 13px;">Personalized 1-click cold messages</p>
                </div>
                <button onclick="closeOutreachModal()" style="background:transparent;border:none;color:var(--text-muted);font-size:22px;cursor:pointer;">&times;</button>
            </div>

            <div class="modal-tabs">
                <button id="tab-li" class="tab-btn active" onclick="switchOutreachTab('li')">💼 LinkedIn Note (&lt;300 chars)</button>
                <button id="tab-email" class="tab-btn" onclick="switchOutreachTab('email')">✉️ Cold Email (Hiring Lead)</button>
                <button id="tab-inmail" class="tab-btn" onclick="switchOutreachTab('inmail')">🎯 Recruiter InMail</button>
                <button id="tab-cl" class="tab-btn" onclick="switchOutreachTab('cl')">📝 Tailored Cover Letter</button>
                <button id="tab-prep" class="tab-btn" onclick="switchOutreachTab('prep')">🧠 Interview Prep (Top 10)</button>
            </div>

            <div id="view-li">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                    <span style="font-size:12px; color:var(--text-muted);">Connection Request Message:</span>
                    <span id="li-char-badge" style="font-size:11px; background:rgba(16,185,129,0.15); color:#34d399; padding:2px 6px; border-radius:4px; font-weight:600;">220 / 300 chars</span>
                </div>
                <div id="text-li" class="outreach-content-box">Loading...</div>
                <button class="btn" onclick="copyModalText('text-li')">📋 Copy LinkedIn Note</button>
            </div>

            <div id="view-email" style="display:none;">
                <div style="margin-bottom:8px;">
                    <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">Recipient Email (Hiring Lead / Recruiter):</div>
                    <input id="text-email-to" type="email" class="input-box" placeholder="e.g. careers@company.com" style="width:100%; margin-bottom:8px;">
                    
                    <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">Subject:</div>
                    <div style="display:flex; gap:8px; margin-bottom:8px;">
                        <input id="text-email-sub" type="text" class="input-box" style="flex:1;">
                        <button class="btn btn-outline" onclick="copyInputVal('text-email-sub')">Copy</button>
                    </div>
                </div>
                <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">Email Body:</div>
                <textarea id="text-email-body" class="outreach-content-box" style="width:100%; min-height:140px; resize:vertical; font-family:inherit; font-size:12px; line-height:1.5;"></textarea>

                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; margin:10px 0; gap:8px;">
                    <div style="display:flex; gap:16px; font-size:12px; color:var(--text-muted);">
                        <label style="display:flex; align-items:center; gap:6px; cursor:pointer;"><input type="checkbox" id="email-attach-resume" checked> 📄 Attach Resume PDF</label>
                        <label style="display:flex; align-items:center; gap:6px; cursor:pointer;"><input type="checkbox" id="email-attach-cover" checked> 📝 Attach Cover Letter</label>
                    </div>
                    <div style="display:flex; gap:8px;">
                        <button class="btn btn-outline" onclick="copyEmailBodyFromTextarea()">📋 Copy Body</button>
                        <button class="btn btn-green" onclick="sendDirectColdEmail()">🚀 Send Cold Email</button>
                    </div>
                </div>
                <div id="email-dispatch-status" style="display:none; padding:8px 12px; border-radius:6px; font-size:12px; margin-top:8px;"></div>
            </div>

            <div id="view-inmail" style="display:none;">
                <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">InMail Message:</div>
                <div id="text-inmail" class="outreach-content-box">Loading...</div>
                <button class="btn" onclick="copyModalText('text-inmail')">📋 Copy InMail</button>
            </div>

            <div id="view-cl" style="display:none;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-size:12px; color:var(--text-muted);">Tailored Cover Letter:</span>
                    <a id="cl-pdf-link" href="#" target="_blank" class="btn btn-outline" style="font-size:11px; text-decoration:none;">📄 View PDF ↗</a>
                </div>
                <div id="text-cl" class="outreach-content-box" style="min-height:160px;">Loading...</div>
                <button class="btn" onclick="copyModalText('text-cl')">📋 Copy Cover Letter</button>
            </div>

            <div id="view-prep" style="display:none;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-size:12px; color:var(--text-muted);">Technical Q&amp;A and STAR Talking Points:</span>
                    <button class="btn" onclick="copyModalText('text-prep')">📋 Copy Prep Notes</button>
                </div>
                <div id="text-prep" class="outreach-content-box" style="min-height:220px; font-size:12px;">Loading...</div>
            </div>
        </div>
    </div>

    <!-- Notification / SMTP Modal -->
    <div id="notif-modal" class="modal-overlay" onclick="if(event.target===this) closeNotifModal()">
        <div class="modal-box" style="max-width: 580px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
                <div>
                    <h2 style="margin: 0; font-size: 18px; color: var(--accent);">⚙️ Alerts &amp; Direct Email Setup</h2>
                    <p style="margin: 4px 0 0 0; color: var(--text-muted); font-size: 13px;">Telegram mobile alerts, Discord, and Gmail SMTP cold emailing</p>
                </div>
                <button onclick="closeNotifModal()" style="background:transparent;border:none;color:var(--text-muted);font-size:22px;cursor:pointer;">&times;</button>
            </div>

            <form onsubmit="event.preventDefault(); saveNotificationSettings(); return false;" style="display:flex; flex-direction:column; gap:12px;">
                <div style="background:#050914; padding:12px; border-radius:8px; border:1px solid var(--card-border);">
                    <h4 style="margin:0 0 6px 0; color:#38bdf8; font-size:13px;">✈️ Telegram Bot Alerts</h4>
                    <label style="font-size:11px; color:var(--text-muted); display:block; margin-bottom:4px;">Telegram Bot Token:</label>
                    <input type="text" id="tg-token-input" class="input-box" placeholder="e.g. 123456789:ABCdefGhIJKlmNoPQRstuVWXyz" style="width:100%; margin-bottom:8px;">
                    <label style="font-size:11px; color:var(--text-muted); display:block; margin-bottom:4px;">Telegram Chat ID:</label>
                    <input type="text" id="tg-chat-input" class="input-box" placeholder="e.g. 987654321" style="width:100%;">
                </div>

                <div style="background:#050914; padding:12px; border-radius:8px; border:1px solid var(--card-border);">
                    <h4 style="margin:0 0 6px 0; color:#10b981; font-size:13px;">📬 Gmail SMTP (1-Click Cold Email)</h4>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:8px;">
                        <div>
                            <label style="font-size:11px; color:var(--text-muted); display:block; margin-bottom:4px;">Sender Gmail:</label>
                            <input type="email" id="smtp-user-input" class="input-box" placeholder="youremail@gmail.com" style="width:100%;">
                        </div>
                        <div>
                            <label style="font-size:11px; color:var(--text-muted); display:block; margin-bottom:4px;">App Password (16-char):</label>
                            <input type="password" id="smtp-pass-input" autocomplete="current-password" class="input-box" placeholder="xxxx xxxx xxxx xxxx" style="width:100%;">
                        </div>
                    </div>
                    <label style="font-size:11px; color:var(--text-muted); display:block; margin-bottom:4px;">Sender Full Name:</label>
                    <input type="text" id="smtp-name-input" class="input-box" placeholder="Sasi Kumar Reddy Chintala" style="width:100%;">
                </div>

                <div style="display:flex; justify-content:space-between; gap:10px; margin-top:8px;">
                    <button type="button" class="btn btn-outline" onclick="sendTestAlert()">🧪 Test Alert</button>
                    <button type="submit" class="btn btn-green">💾 Save Credentials</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Header Navigation -->
    <div class="header">
        <div class="brand-container">
            <div class="brand-logo">
                <svg viewBox="0 0 64 64" fill="none">
                    <path d="M22 23V17C22 14.7909 23.7909 13 26 13H38C40.2091 13 42 14.7909 42 17V23" stroke="#ffffff" stroke-width="3.5" stroke-linecap="round"/>
                    <rect x="13" y="23" width="38" height="27" rx="7" fill="#0b1426" stroke="#ffffff" stroke-width="2.5"/>
                    <circle cx="32" cy="35" r="4.5" fill="#38bdf8"/>
                    <path d="M49 10L50.5 14L54.5 15.5L50.5 17L49 21L47.5 17L43.5 15.5L47.5 14L49 10Z" fill="#38bdf8"/>
                </svg>
            </div>
            <div>
                <h1 class="brand-title">Elevora AI <span class="live-tag">0–2 Yrs Engine</span></h1>
                <p id="candidate-info" class="brand-subtitle">Candidate: Loading profile...</p>
            </div>
        </div>

        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <button class="btn btn-outline" id="btn-header-history" onclick="switchMainTab('history')">📁 Job History (<span id="header-history-count">0</span>)</button>
            <input type="file" id="resume-file-input" accept=".pdf,.docx" style="display: none;" onchange="handleResumeUpload(this.files[0])">
            <button class="btn btn-outline" onclick="document.getElementById('resume-file-input').click()">📄 Upload Resume</button>
            <button class="btn btn-outline" onclick="syncTrackerNow()">📊 Sync Tracker</button>
            <button class="btn btn-outline" onclick="openNotifModal()">⚙️ Settings</button>
            <button class="btn btn-green" onclick="runFullPipeline()">🚀 Auto-Apply</button>
            <button class="btn" style="background: rgba(239, 68, 68, 0.15); border: 1px solid #ef4444; color: #f87171;" onclick="clearAllData()">🗑️ Clear Data</button>
        </div>
    </div>

    <!-- Search Card -->
    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <h2 style="font-size: 15px; margin: 0; color: var(--accent);">⚡ 1-Click Multi-Board Search (Ashby, LinkedIn, Wellfound, Turing, Internshala, Cutshort, Instahyre, Naukri)</h2>
        </div>
        
        <!-- Categorized Role Chips -->
        <div style="margin-top:10px; display:flex; flex-direction:column; gap:8px;">
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                <span style="font-size:11px; color:#38bdf8; font-weight:700; text-transform:uppercase; min-width:85px;">🎯 Experience:</span>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#38bdf8; color:#7dd3fc;" onclick="setExpPreset('1-2 years')">🎯 1-2 Years Exp</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#34d399; color:#6ee7b7;" onclick="setExpPreset('Fresher 0-1 year')">🌱 Fresher / 0-1 Year</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#818cf8; color:#a5b4fc;" onclick="setExpPreset('Junior 0-2 years')">🚀 Junior / 0-2 Years</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#f472b6; color:#fbcfe8;" onclick="setSearchPreset('Junior AI Engineer 0-2 years')">🤖 Jr AI Engineer</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#fbbf24; color:#fde68a;" onclick="setSearchPreset('Junior Python Developer 1-2 years')">🐍 Jr Python</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#2dd4bf; color:#99f6e4;" onclick="setSearchPreset('Junior Data Analyst 0-2 years')">📊 Jr Data Analyst</button>
            </div>
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                <span style="font-size:11px; color:#818cf8; font-weight:700; text-transform:uppercase; min-width:85px;">🤖 AI &amp; Data:</span>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#818cf8; color:#a5b4fc;" onclick="setSearchPreset('AI Engineer 0-2 years')">🤖 AI Engineer</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#f472b6; color:#fbcfe8;" onclick="setSearchPreset('Generative AI Python 1-2 years')">⚡ GenAI &amp; LLM Dev</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#38bdf8; color:#7dd3fc;" onclick="setSearchPreset('Machine Learning Engineer 0-2 years')">🧠 ML Engineer</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#34d399; color:#6ee7b7;" onclick="setSearchPreset('Data Analyst 0-2 years')">📊 Data Analyst</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#c084fc; color:#e9d5ff;" onclick="setSearchPreset('AI Agent Developer LangChain 1-2 years')">🤖 AI Agent Dev</button>
            </div>
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                <span style="font-size:11px; color:#34d399; font-weight:700; text-transform:uppercase; min-width:85px;">💻 Software:</span>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#34d399; color:#a7f3d0;" onclick="setSearchPreset('Associate Software Developer 0-2 years')">🚀 Associate SWE</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#fbbf24; color:#fde68a;" onclick="setSearchPreset('Junior Python Developer 0-2 years')">🐍 Jr Python Dev</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#60a5fa; color:#bfdbfe;" onclick="setSearchPreset('Backend Developer FastAPI 1-2 years')">💼 Backend Developer</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#2dd4bf; color:#99f6e4;" onclick="setSearchPreset('Full Stack Python Developer 0-2 years')">🌐 Full Stack Python</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#94a3b8; color:#cbd5e1;" onclick="setSearchPreset('Software Engineer Fresher 0-2 years')">🎯 Fresher / Entry</button>
            </div>
        </div>

        <div class="search-bar" style="margin-top:14px;">
            <select id="search-query" class="input-box" style="flex: 2; min-width: 240px; cursor: pointer;">
                <optgroup label="🔥 Most Popular / Target Roles">
                    <option value="Junior Python Developer 0-2 years" selected>🐍 Junior Python Developer (0-2 Yrs)</option>
                    <option value="Junior AI Engineer 0-2 years">🤖 Junior AI Engineer (0-2 Yrs)</option>
                    <option value="Generative AI Python 1-2 years">⚡ GenAI &amp; LLM Developer (1-2 Yrs)</option>
                    <option value="Associate Software Developer 0-2 years">🚀 Associate Software Engineer (0-2 Yrs)</option>
                    <option value="Junior Data Analyst 0-2 years">📊 Junior Data Analyst (0-2 Yrs)</option>
                    <option value="Junior Data Engineer 0-2 years">🛠️ Junior Data Engineer (0-2 Yrs)</option>
                </optgroup>
                <optgroup label="🤖 AI &amp; Machine Learning">
                    <option value="AI Engineer 0-2 years">🤖 AI Engineer (0-2 Yrs)</option>
                    <option value="Machine Learning Engineer 0-2 years">🧠 Machine Learning Engineer (0-2 Yrs)</option>
                    <option value="AI Agent Developer LangChain 1-2 years">🧠 AI Agent Developer (1-2 Yrs)</option>
                    <option value="Prompt Engineer RAG 0-2 years">🔮 Prompt Engineer &amp; RAG (0-2 Yrs)</option>
                </optgroup>
                <optgroup label="💻 Software &amp; Backend">
                    <option value="Python Developer 1-2 years">🐍 Python Developer (1-2 Yrs)</option>
                    <option value="Backend Developer FastAPI 1-2 years">💼 Backend Developer (FastAPI) (1-2 Yrs)</option>
                    <option value="Full Stack Python Developer 0-2 years">🌐 Full Stack Python Developer (0-2 Yrs)</option>
                    <option value="Software Development Engineer SDE 1">💻 SDE-1 / Software Developer 1 (0-2 Yrs)</option>
                </optgroup>
            </select>

            <select id="search-location" class="input-box" style="flex: 1.5; min-width: 190px; cursor: pointer;">
                <optgroup label="🇮🇳 Top India Tech Hubs">
                    <option value="Bengaluru" selected>📍 Bengaluru / Bangalore</option>
                    <option value="Hyderabad">📍 Hyderabad</option>
                    <option value="Pune">📍 Pune</option>
                    <option value="Delhi NCR (Gurgaon / Noida)">📍 Delhi NCR (Gurgaon / Noida)</option>
                    <option value="Mumbai">📍 Mumbai / Navi Mumbai</option>
                    <option value="Chennai">📍 Chennai</option>
                    <option value="India">🇮🇳 Pan India / Any Location</option>
                </optgroup>
                <optgroup label="🌐 Remote &amp; Global">
                    <option value="Remote">🏠 Remote (India / Work From Home)</option>
                    <option value="Worldwide Remote">🌍 Worldwide Remote / Global</option>
                    <option value="United States Remote">🇺🇸 United States (Remote)</option>
                </optgroup>
            </select>

            <select id="search-exp" class="input-box" style="max-width: 170px; cursor: pointer;">
                <option value="0-2 years" selected>🎯 0–2 Years / Fresher</option>
                <option value="1-2 years">🎯 1–2 Years Exp</option>
                <option value="Fresher 0-1 year">🌱 Fresher (0–1 Yr)</option>
                <option value="all">Any Experience</option>
            </select>
            <select id="search-time" class="input-box" style="max-width: 140px; cursor: pointer;">
                <option value="24h">Past 24 Hours</option>
                <option value="3d" selected>Past 3 Days</option>
                <option value="7d">Past 7 Days</option>
            </select>
            <button class="btn" id="btn-search-score" onclick="searchAndScore()">⚡ Search 0-2 Yrs Jobs</button>
        </div>
        <p id="search-status" style="font-size: 13px; color: var(--accent); margin: 10px 0 0 0; font-weight: 500;"></p>
    </div>

    <!-- Live Activity Log Terminal -->
    <div>
        <div class="log-panel-header">
            <span style="font-size: 12px; color: var(--text-muted); font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">📡 Live Agent Activity Feed</span>
            <div style="display:flex;gap:10px;align-items:center;">
                <span id="log-status-dot" class="live-tag" style="padding: 2px 7px; font-size:10px;">IDLE</span>
                <button onclick="document.getElementById('log-panel').innerHTML='';" class="btn btn-outline" style="padding:2px 8px;font-size:11px;">Clear</button>
            </div>
        </div>
        <div id="log-panel" class="log-panel">
            <div class="log-line" style="color:#475569;">Ready for agent activity... Click 'Search 0-2 Yrs Jobs' to stream live discovery.</div>
        </div>
    </div>

    <!-- Metrics Stats Grid -->
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">Total Discovered</div>
            <div class="stat-val" id="stat-total">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Qualified (Fit Score &ge; 70)</div>
            <div class="stat-val" id="stat-qualified" style="color: #38bdf8;">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Tailored Resumes Ready</div>
            <div class="stat-val" id="stat-resumes" style="color: #fbbf24;">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Ready / Submitted</div>
            <div class="stat-val" id="stat-submitted" style="color: #34d399;">0</div>
        </div>
    </div>

    <!-- Main Results & History Container -->
    <div class="card">
        <!-- View Navigation Tabs -->
        <div class="view-tabs">
            <button id="vtab-live" class="v-tab-btn active" onclick="switchMainTab('live')">
                ⚡ Current Search Stream <span class="tab-count" id="count-live">0</span>
            </button>
            <button id="vtab-history" class="v-tab-btn" onclick="switchMainTab('history')">
                📁 Job History &amp; Archive <span class="tab-count" id="count-history">0</span>
            </button>
            <button id="vtab-qualified" class="v-tab-btn" onclick="switchMainTab('qualified')">
                ⭐ Qualified Match (&ge;70) <span class="tab-count" id="count-qualified">0</span>
            </button>
            <button id="vtab-resumes" class="v-tab-btn" onclick="switchMainTab('resumes')">
                📄 Tailored Resumes Ready <span class="tab-count" id="count-resumes">0</span>
            </button>

            <!-- Search / Filter Box for History -->
            <div id="history-filter-box" style="margin-left:auto; display:none; gap:8px; align-items:center;">
                <input type="text" id="history-search-input" class="input-box" placeholder="🔍 Search company or title..." style="font-size:12px; padding:6px 10px;" oninput="renderCurrentTable()">
                <button class="btn btn-outline" style="font-size:11px; padding:4px 8px;" onclick="clearData()">🧹 Clear</button>
            </div>
        </div>

        <!-- Scanning Radar Active Banner -->
        <div id="radar-banner" class="radar-box">
            <div style="display:flex; align-items:center; gap:10px;">
                <div class="radar-dot"></div>
                <div>
                    <strong style="color:#7dd3fc; font-size:13px;">📡 Live Multi-Board Discovery in Progress...</strong>
                    <div style="font-size:11px; color:#94a3b8; margin-top:2px;">Scanning Ashby, LinkedIn, Wellfound, Turing, Cutshort, Instahyre, Naukri... Jobs will appear below as they are found.</div>
                </div>
            </div>
            <div id="radar-counter" style="font-size:12px; font-weight:700; color:#38bdf8; background:rgba(56,189,248,0.15); padding:4px 10px; border-radius:6px;">
                0 found this run
            </div>
        </div>

        <!-- Table -->
        <div style="overflow-x: auto;">
            <table>
                <thead>
                    <tr>
                        <th style="width: 50px;">ID</th>
                        <th style="width: 130px;">Platform</th>
                        <th>Company &amp; Location</th>
                        <th>Job Title</th>
                        <th style="width: 140px;">Resume Fit Score</th>
                        <th style="width: 100px;">Decision</th>
                        <th style="width: 120px;">Status</th>
                        <th style="width: 130px;">Tailored Resume</th>
                        <th style="width: 150px;">Quick Actions</th>
                        <th style="width: 70px;">Link</th>
                    </tr>
                </thead>
                <tbody id="app-rows">
                    <!-- Populated dynamically -->
                </tbody>
            </table>
        </div>
    </div>

    <script>
        let allJobsList = [];
        let liveSessionJobIds = new Set();
        let currentViewMode = 'live'; // 'live', 'history', 'qualified', 'resumes'
        let isSearching = false;
        let searchStartTime = null;
        let highestSeenJobId = 0;
        let pollInterval = null;

        let currentOutreachData = null;
        let currentJobId = null;

        // Switch main view tab
        function switchMainTab(mode) {
            currentViewMode = mode;
            document.querySelectorAll('.v-tab-btn').forEach(btn => btn.classList.remove('active'));
            const activeBtn = document.getElementById(`vtab-${mode}`);
            if (activeBtn) activeBtn.classList.add('active');

            const filterBox = document.getElementById('history-filter-box');
            if (filterBox) {
                filterBox.style.display = (mode === 'history' || mode === 'qualified' || mode === 'resumes') ? 'flex' : 'none';
            }

            renderCurrentTable();
        }

        function renderCurrentTable() {
            const tbody = document.getElementById('app-rows');
            let displayJobs = [];
            const searchFilter = (document.getElementById('history-search-input')?.value || '').toLowerCase().trim();
            const currentSelectedRole = (document.getElementById('search-query')?.value || '').toLowerCase().trim();

            if (currentViewMode === 'live') {
                if (liveSessionJobIds.size > 0) {
                    displayJobs = allJobsList.filter(j => liveSessionJobIds.has(j.job_id));
                } else {
                    // Extract core terms from query (e.g. "software", "developer", "python", "ai", "engineer")
                    const terms = currentSelectedRole.split(' ').filter(w => w.length > 2 && !['0-2', '1-2', 'years', 'yrs', 'fresher', 'most', 'popular'].includes(w));
                    displayJobs = allJobsList.filter(j => {
                        const text = `${j.title} ${j.company} ${j.source}`.toLowerCase();
                        return terms.some(t => text.includes(t));
                    });
                    if (displayJobs.length === 0) {
                        displayJobs = allJobsList.slice(0, 50);
                    }
                }
            } else if (currentViewMode === 'history') {
                displayJobs = allJobsList.filter(j => {
                    if (!searchFilter) return true;
                    return (j.company || '').toLowerCase().includes(searchFilter) ||
                           (j.title || '').toLowerCase().includes(searchFilter) ||
                           (j.source || '').toLowerCase().includes(searchFilter);
                });
            } else if (currentViewMode === 'qualified') {
                displayJobs = allJobsList.filter(j => j.decision === 'HIGH' || j.decision === 'VERY_HIGH' || j.decision === 'QUALIFIED' || (j.match_score && j.match_score >= 70));
            } else if (currentViewMode === 'resumes') {
                displayJobs = allJobsList.filter(j => j.tailored_resume_path);
            }

            // LinkedIn-style ranking: Always sort by highest resume match fit first
            displayJobs.sort((a, b) => (b.match_score || 0) - (a.match_score || 0) || b.job_id - a.job_id);

            if (displayJobs.length === 0) {
                tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; padding: 30px; color: #64748b;">No matching jobs in this view.</td></tr>`;
                return;
            }

            tbody.innerHTML = displayJobs.map(a => renderJobRowHtml(a, liveSessionJobIds.has(a.job_id))).join('');
        }

        function renderJobRowHtml(a, isNewInSession = false) {
            let scoreHtml = '<span style="color:#64748b; font-size:11px;">⏳ Scoring...</span>';
            if (a.match_score !== null && a.match_score !== undefined) {
                const s = a.match_score;
                const badgeColor = s >= 80 ? '#34d399' : s >= 70 ? '#38bdf8' : '#fbbf24';
                const badgeBg = s >= 80 ? 'rgba(16,185,129,0.18)' : s >= 70 ? 'rgba(56,189,248,0.18)' : 'rgba(245,158,11,0.18)';
                const grade = s >= 85 ? 'A+ Top' : s >= 75 ? 'Strong' : 'Good';
                scoreHtml = `<span style="background:${badgeBg}; color:${badgeColor}; padding:3px 8px; border-radius:5px; font-weight:700; font-size:11px; white-space:nowrap;">🎯 ${s}% (${grade})</span>`;
            }

            let resumeHtml = `<button onclick="tailorJobNow(${a.job_id}, this)" class="btn btn-outline" style="font-size:11px; padding:3px 8px; color:#38bdf8; border-color:rgba(56,189,248,0.3); cursor:pointer;">⚡ Tailor PDF</button>`;
            if (a.tailored_resume_path) {
                resumeHtml = `<a href="/api/view-resume?file=${encodeURIComponent(a.tailored_resume_path)}" target="_blank" class="btn btn-outline" style="font-size:11px; padding:3px 8px; color:#fbbf24; border-color:rgba(245,158,11,0.3); text-decoration:none; font-weight:600;">📄 Tailored PDF ↗</a>`;
            }

            let srcBadge = `<span style="font-size: 10px; text-transform: uppercase; color: var(--accent);">${a.source || 'Live'}</span>`;
            const srcLow = (a.source || '').toLowerCase();
            if (srcLow.includes('python_org')) {
                srcBadge = `<span style="background:rgba(16,185,129,0.18);color:#34d399;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;">★ Python.org</span>`;
            } else if (srcLow.includes('ashby')) {
                srcBadge = `<span style="background:rgba(16,185,129,0.22);color:#10b981;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;">⭐ Ashby Direct</span>`;
            } else if (srcLow.includes('wellfound')) {
                srcBadge = `<span style="background:rgba(239,68,68,0.18);color:#f87171;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;">🦄 Wellfound</span>`;
            } else if (srcLow.includes('turing')) {
                srcBadge = `<span style="background:rgba(16,185,129,0.2);color:#34d399;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;">🌍 Turing</span>`;
            } else if (srcLow.includes('cutshort')) {
                srcBadge = `<span style="background:rgba(236,72,153,0.18);color:#f472b6;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;">🚀 Cutshort</span>`;
            } else if (srcLow.includes('instahyre')) {
                srcBadge = `<span style="background:rgba(168,85,247,0.18);color:#c084fc;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;">⚡ Instahyre</span>`;
            } else if (srcLow.includes('internshala')) {
                srcBadge = `<span style="background:rgba(59,130,246,0.18);color:#60a5fa;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;">🎓 Internshala</span>`;
            } else if (srcLow.includes('linkedin')) {
                srcBadge = `<span style="background:rgba(148,163,184,0.15);color:#cbd5e1;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;">🔗 LinkedIn</span>`;
            }

            const outreachBtn = `<button onclick="openOutreachModal(${a.job_id})" class="btn btn-outline" style="font-size:11px; padding:3px 8px; color:#a5b4fc; border-color:rgba(99,102,241,0.3);">✉️ Note</button>`;
            const applyBtn = `<button onclick="applyJobNow(${a.job_id}, this)" class="btn btn-green" style="font-size:11px; padding:3px 8px;">🚀 Apply</button>`;
            const newPill = isNewInSession ? `<span style="background:rgba(56,189,248,0.25);color:#38bdf8;font-size:9px;padding:2px 5px;border-radius:4px;margin-left:6px;font-weight:700;">NEW</span>` : '';

            return `
            <tr class="${isNewInSession ? 'row-stream-new' : ''}">
                <td style="color:#64748b; font-size:12px;">#${a.job_id}</td>
                <td>${srcBadge}</td>
                <td>
                    <strong style="color:var(--text);">${a.company}</strong>${newPill}
                    <div style="font-size:11px; color:#64748b; margin-top:2px;">📍 ${a.location || 'Bengaluru'}</div>
                </td>
                <td style="font-weight:600;"><a href="${a.url || '#'}" target="_blank" style="color:#e2e8f0; text-decoration:none;">${a.title} ↗</a></td>
                <td>${scoreHtml}</td>
                <td><strong style="color:#94a3b8; font-size:12px;">${a.decision || 'QUALIFIED'}</strong></td>
                <td><span class="badge badge-${a.status}">${a.status}</span></td>
                <td>${resumeHtml}</td>
                <td>
                    <div style="display:flex; gap:6px; align-items:center;">
                        ${applyBtn}
                        ${outreachBtn}
                    </div>
                </td>
                <td><a href="${a.url || '#'}" target="_blank" style="color:#38bdf8; text-decoration:none; font-size:12px; font-weight:600;">View ↗</a></td>
            </tr>`;
        }

        async function tailorJobNow(jobId, btn) {
            btn.disabled = true;
            btn.innerText = "⏳ Tailoring...";
            try {
                const res = await fetch('/api/tailor-job', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({job_id: jobId})
                });
                const d = await res.json();
                if (d.status === 'SUCCESS' && d.tailored_resume_path) {
                    showToast("Resume tailored successfully!");
                    btn.outerHTML = `<a href="/api/view-resume?file=${encodeURIComponent(d.tailored_resume_path)}" target="_blank" class="btn btn-outline" style="font-size:11px; padding:3px 8px; color:#fbbf24; border-color:rgba(245,158,11,0.3); text-decoration:none; font-weight:600;">📄 Tailored PDF ↗</a>`;
                    await loadData();
                } else {
                    btn.innerText = "❌ Failed";
                    showToast(d.message || "Failed to tailor resume");
                }
            } catch(e) {
                btn.innerText = "❌ Error";
                showToast(e);
            }
        }

        async function applyJobNow(jobId, btn) {
            btn.disabled = true;
            btn.innerText = "⏳ Launching...";
            try {
                const res = await fetch('/api/apply-job', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({job_id: jobId})
                });
                const d = await res.json();
                if (d.status === 'STARTED') {
                    showToast("Stealth application launched! Check live feed.");
                    btn.innerText = "🚀 Applying...";
                    setTimeout(() => { btn.innerText = "✅ In Progress"; }, 3000);
                }
            } catch(e) {
                showToast("Apply error: " + e);
                btn.innerText = "🚀 Apply";
                btn.disabled = false;
            }
        }

        async function loadProfile() {
            try {
                const res = await fetch('/api/profile');
                const p = await res.json();
                if (p && p.contact_info) {
                    document.getElementById('candidate-info').innerText = `Candidate: ${p.contact_info.full_name} | ${p.contact_info.email} | ${p.contact_info.location || 'Bengaluru, India'}`;
                }
            } catch (e) {
                console.error(e);
            }
        }

        async function loadData() {
            try {
                const res = await fetch('/api/jobs');
                const apps = await res.json();
                allJobsList = apps || [];

                // Track highest known ID
                allJobsList.forEach(j => {
                    if (j.job_id > highestSeenJobId) highestSeenJobId = j.job_id;
                });

                // Update Stats
                const total = allJobsList.length;
                const qual = allJobsList.filter(a => a.decision === 'HIGH' || a.decision === 'VERY_HIGH' || (a.match_score && a.match_score >= 70)).length;
                const resCount = allJobsList.filter(a => a.tailored_resume_path).length;
                const subCount = allJobsList.filter(a => a.status === 'READY_TO_SUBMIT' || a.status === 'SUBMITTED').length;

                document.getElementById('stat-total').innerText = total;
                document.getElementById('stat-qualified').innerText = qual;
                document.getElementById('stat-resumes').innerText = resCount;
                document.getElementById('stat-submitted').innerText = subCount;

                // Update Tab Badges
                document.getElementById('count-live').innerText = liveSessionJobIds.size;
                document.getElementById('count-history').innerText = total;
                document.getElementById('count-qualified').innerText = qual;
                document.getElementById('count-resumes').innerText = resCount;
                document.getElementById('header-history-count').innerText = total;

                // If searching, check for newly added jobs and add to live session set
                if (isSearching) {
                    allJobsList.forEach(j => {
                        if (searchStartTime && j.job_id > (searchStartTime.baseMaxId || 0)) {
                            liveSessionJobIds.add(j.job_id);
                        }
                    });
                    document.getElementById('radar-counter').innerText = `${liveSessionJobIds.size} found this run`;
                }

                renderCurrentTable();
            } catch (e) {
                console.error(e);
            }
        }

        async function searchAndScore() {
            let query = document.getElementById('search-query').value;
            const location = document.getElementById('search-location').value;
            const time_range = document.getElementById('search-time').value;
            const exp = document.getElementById('search-exp') ? document.getElementById('search-exp').value : '';
            const status = document.getElementById('search-status');
            const btn = document.getElementById('btn-search-score');
            const radar = document.getElementById('radar-banner');

            if (exp && exp !== 'all' && !query.toLowerCase().includes('year') && !query.toLowerCase().includes('fresher')) {
                query = `${query} ${exp}`;
            }

            // Switch to Live Stream tab
            switchMainTab('live');
            liveSessionJobIds.clear();
            searchStartTime = { time: new Date(), baseMaxId: highestSeenJobId };
            isSearching = true;

            radar.classList.add('active');
            status.innerText = `⏳ Scanning 28+ portals for '${query}' in '${location}'. Jobs will appear in real time below...`;
            btn.disabled = true;

            try {
                await fetch('/api/search-and-match', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query, location, time_range})
                });

                if (pollInterval) clearInterval(pollInterval);
                let pollCount = 0;
                pollInterval = setInterval(async () => {
                    await loadData();
                    pollCount++;
                    if (pollCount > 80) { // ~2.5 mins
                        clearInterval(pollInterval);
                        isSearching = false;
                        radar.classList.remove('active');
                        btn.disabled = false;
                        status.innerText = `✅ Discovery complete! Found ${liveSessionJobIds.size} new jobs in this run.`;
                    }
                }, 1500);
            } catch (e) {
                status.innerText = `❌ Error: ${e}`;
                btn.disabled = false;
                isSearching = false;
                radar.classList.remove('active');
            }
        }

        function setExpPreset(exp) {
            const expSelect = document.getElementById('search-exp');
            if (expSelect) {
                for (let i = 0; i < expSelect.options.length; i++) {
                    if (expSelect.options[i].value === exp || expSelect.options[i].value.includes(exp)) {
                        expSelect.selectedIndex = i;
                        break;
                    }
                }
            }
            searchAndScore();
        }

        function setSearchPreset(role) {
            const querySelect = document.getElementById('search-query');
            if (querySelect) {
                let found = false;
                for (let i = 0; i < querySelect.options.length; i++) {
                    if (querySelect.options[i].value === role || querySelect.options[i].value.toLowerCase().includes(role.toLowerCase())) {
                        querySelect.selectedIndex = i;
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    const opt = new Option(`🎯 ${role}`, role, true, true);
                    querySelect.add(opt, 0);
                    querySelect.selectedIndex = 0;
                }
            }
            searchAndScore();
        }

        async function openOutreachModal(jobId) {
            currentJobId = jobId;
            document.getElementById('outreach-modal').classList.add('open');
            document.getElementById('text-li').innerText = "⏳ Generating personalized note...";
            document.getElementById('text-email-body').value = "⏳ Generating personalized email...";
            document.getElementById('text-email-to').value = "";
            document.getElementById('email-dispatch-status').style.display = 'none';
            document.getElementById('text-inmail').innerText = "⏳ Generating personalized InMail...";
            document.getElementById('text-cl').innerText = "⏳ Compiling tailored cover letter & PDF...";
            document.getElementById('text-email-sub').value = "Loading...";

            try {
                const res = await fetch(`/api/outreach?job_id=${jobId}`);
                const resJson = await res.json();
                if (resJson.status === 'SUCCESS') {
                    currentOutreachData = resJson.data;
                    document.getElementById('modal-company-title').innerText = `Outreach & Prep: ${currentOutreachData.company}`;
                    document.getElementById('modal-role-subtitle').innerText = `Role: ${currentOutreachData.title}`;

                    document.getElementById('text-li').innerText = currentOutreachData.linkedin_note;
                    document.getElementById('li-char-badge').innerText = `${currentOutreachData.linkedin_char_count} / 300 chars`;
                    document.getElementById('text-email-sub').value = currentOutreachData.email_subject;
                    document.getElementById('text-email-body').value = currentOutreachData.email_body;
                    document.getElementById('text-inmail').innerText = currentOutreachData.recruiter_inmail;
                }

                const clRes = await fetch(`/api/cover-letter?job_id=${jobId}`);
                const clJson = await clRes.json();
                if (clJson.status === 'SUCCESS') {
                    document.getElementById('text-cl').innerText = clJson.text;
                    document.getElementById('cl-pdf-link').href = clJson.pdf_url;
                }

                const prepRes = await fetch(`/api/interview-prep?job_id=${jobId}`);
                const prepJson = await prepRes.json();
                if (prepJson.status === 'SUCCESS') {
                    let prepFormatted = `🎯 TOP 10 PREDICTED TECHNICAL QUESTIONS & MODEL TALKING POINTS\n` +
                                        `==============================================================\n\n`;
                    prepJson.questions.forEach((q, idx) => {
                        prepFormatted += `Q${idx+1}. [${q.category}]\n${q.question}\n\nKey Talking Points:\n${q.talking_points}\n\n--------------------------------------------------------------\n\n`;
                    });
                    document.getElementById('text-prep').innerText = prepFormatted;
                }
            } catch (e) {
                console.error(e);
            }
        }

        async function sendDirectColdEmail() {
            const toEmail = document.getElementById('text-email-to').value.trim();
            const subject = document.getElementById('text-email-sub').value.trim();
            const body = document.getElementById('text-email-body').value.trim();
            const attachResume = document.getElementById('email-attach-resume').checked;
            const attachCover = document.getElementById('email-attach-cover').checked;
            const statusDiv = document.getElementById('email-dispatch-status');

            if (!toEmail) {
                alert("Please enter recipient email.");
                return;
            }

            statusDiv.style.display = 'block';
            statusDiv.style.background = 'rgba(56,189,248,0.15)';
            statusDiv.style.color = '#38bdf8';
            statusDiv.innerHTML = "⏳ Sending cold email via SMTP...";

            try {
                const res = await fetch('/api/email/send', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        job_id: currentJobId,
                        to_email: toEmail,
                        subject: subject,
                        body: body,
                        attach_resume: attachResume,
                        attach_cover: attachCover
                    })
                });
                const data = await res.json();
                if (data.status === 'SUCCESS') {
                    statusDiv.style.background = 'rgba(16,185,129,0.18)';
                    statusDiv.style.color = '#34d399';
                    statusDiv.innerHTML = `✅ ${data.message}`;
                    showToast("Cold email dispatched!");
                    await loadData();
                } else {
                    statusDiv.style.background = 'rgba(239,68,68,0.18)';
                    statusDiv.style.color = '#f87171';
                    statusDiv.innerHTML = `❌ ${data.error || 'Failed'}`;
                }
            } catch(e) {
                statusDiv.innerHTML = `❌ ${e}`;
            }
        }

        function copyEmailBodyFromTextarea() {
            navigator.clipboard.writeText(document.getElementById('text-email-body').value);
            showToast("Copied email body!");
        }

        function closeOutreachModal() {
            document.getElementById('outreach-modal').classList.remove('open');
        }

        function switchOutreachTab(tab) {
            ['li', 'email', 'inmail', 'cl', 'prep'].forEach(t => {
                document.getElementById(`tab-${t}`)?.classList.remove('active');
                const v = document.getElementById(`view-${t}`);
                if (v) v.style.display = 'none';
            });
            document.getElementById(`tab-${tab}`)?.classList.add('active');
            const target = document.getElementById(`view-${tab}`);
            if (target) target.style.display = 'block';
        }

        function showToast(msg = "Copied to clipboard!") {
            const toast = document.getElementById('copy-toast');
            toast.innerText = `✅ ${msg}`;
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; }, 2500);
        }

        function copyModalText(elementId) {
            navigator.clipboard.writeText(document.getElementById(elementId).innerText);
            showToast("Copied to clipboard!");
        }

        function copyInputVal(elementId) {
            navigator.clipboard.writeText(document.getElementById(elementId).value);
            showToast("Copied to clipboard!");
        }

        async function openNotifModal() {
            document.getElementById('notif-modal').classList.add('open');
            try {
                const res = await fetch('/api/notifications');
                const d = await res.json();
                if (d.tg_token) document.getElementById('tg-token-input').value = d.tg_token;
                if (d.tg_chat_id) document.getElementById('tg-chat-input').value = d.tg_chat_id;
                if (d.smtp_user) document.getElementById('smtp-user-input').value = d.smtp_user;
                if (d.smtp_password) document.getElementById('smtp-pass-input').value = d.smtp_password;
                if (d.smtp_from_name) document.getElementById('smtp-name-input').value = d.smtp_from_name;
            } catch(e) {}
        }

        function closeNotifModal() {
            document.getElementById('notif-modal').classList.remove('open');
        }

        async function saveNotificationSettings() {
            const tgToken = document.getElementById('tg-token-input').value.trim();
            const tgChat = document.getElementById('tg-chat-input').value.trim();
            const smtpUser = document.getElementById('smtp-user-input').value.trim();
            const smtpPass = document.getElementById('smtp-pass-input').value.trim();
            const smtpName = document.getElementById('smtp-name-input').value.trim();

            const res = await fetch('/api/notifications', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    tg_token: tgToken,
                    tg_chat_id: tgChat,
                    smtp_user: smtpUser,
                    smtp_password: smtpPass,
                    smtp_from_name: smtpName
                })
            });
            const data = await res.json();
            if (data.status === 'SUCCESS') {
                showToast("Settings saved!");
                closeNotifModal();
            } else {
                alert("Failed: " + (data.error || 'Unknown error'));
            }
        }

        async function sendTestAlert() {
            showToast("Sending test alert...");
            const res = await fetch('/api/notifications/test', {method: 'POST'});
            const data = await res.json();
            if (data.status === 'SUCCESS') showToast("Test alert dispatched!");
            else alert("Test failed: " + (data.error || 'Unknown'));
        }

        async function syncTrackerNow() {
            showToast("Syncing tracker...");
            const res = await fetch('/api/sync/all', {method: 'POST'});
            const data = await res.json();
            if (data.status === 'SUCCESS') showToast("Tracker synced!");
            else alert("Sync notice: " + (data.error || 'Check settings'));
        }

        async function clearAllData() {
            const confirmed = confirm("⚠️ WIPE ALL DATA & RESUMES?\\n\\nThis will permanently delete:\\n• All searched & discovered jobs\\n• All match evaluations & application statuses\\n• All generated tailored PDF resumes from disk\\n\\nYou will start with a fresh, 100% clean slate.");
            if (!confirmed) return;

            showToast("Wiping all jobs and tailored resumes...");
            try {
                const res = await fetch('/api/clear', { method: 'POST' });
                const data = await res.json();
                if (data.status === 'CLEARED') {
                    liveSessionJobIds.clear();
                    showToast(`✅ ${data.message || 'Wiped successfully!'}`);
                    setTimeout(() => {
                        window.location.reload();
                    }, 1200);
                } else {
                    alert("Clear failed: " + (data.error || 'Unknown error'));
                }
            } catch(e) {
                alert("Network error: " + e.message);
            }
        }
        const clearData = clearAllData;

        async function runFullPipeline() {
            const status = document.getElementById('search-status');
            status.innerText = "⏳ Running automated applications in browser. Watch live terminal...";
            try {
                await fetch('/api/run-agent', {method: 'POST'});
            } catch(e) {
                status.innerText = `❌ Error: ${e}`;
            }
        }

        function handleResumeUpload(file) {
            if (!file) return;
            const reader = new FileReader();
            const status = document.getElementById('search-status');
            status.innerText = `⏳ Uploading and parsing ${file.name}...`;
            reader.onload = async function() {
                const base64Content = reader.result.split(',')[1];
                try {
                    const res = await fetch('/api/upload-resume', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ filename: file.name, content_base64: base64Content })
                    });
                    const data = await res.json();
                    if (data.status === 'SUCCESS') {
                        status.innerText = `✅ Resume imported for ${data.profile.contact_info.full_name}!`;
                        await loadProfile();
                    } else {
                        status.innerText = `❌ Upload failed: ${data.error || 'Unknown'}`;
                    }
                } catch(e) {
                    status.innerText = `❌ Error: ${e}`;
                }
            };
            reader.readAsDataURL(file);
        }

        function startLogStream() {
            const panel = document.getElementById('log-panel');
            const dot = document.getElementById('log-status-dot');
            const es = new EventSource('/api/logs');

            es.onmessage = function(event) {
                try {
                    const d = JSON.parse(event.data);
                    const line = document.createElement('div');
                    line.className = 'log-line';

                    let prefix = '';
                    if (d.level === 'WARNING') prefix = '⚠️ ';
                    else if (d.level === 'ERROR') prefix = '❌ ';
                    else if (d.level === 'INFO') prefix = '   ';

                    line.innerHTML = `<span style="color:${d.color};">${prefix}${d.msg.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</span>`;
                    panel.appendChild(line);
                    panel.scrollTop = panel.scrollHeight;
                    while (panel.children.length > 300) panel.removeChild(panel.firstChild);

                    dot.innerText = 'ACTIVE';
                    dot.style.color = '#34d399';
                } catch(e) {}
            };

            es.onerror = function() {
                dot.innerText = 'RECONNECTING';
                dot.style.color = '#fbbf24';
            };
        }

        loadProfile();
        loadData();
        startLogStream();
    </script>
</body>
</html>
"""

class AgentDashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/favicon.ico", "/favicon.svg"):
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.end_headers()
            self.wfile.write(FAVICON_SVG.encode("utf-8"))
            return

        if path in ("/health", "/healthz", "/ping", "/api/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","uptime":"live","service":"sasi_job_application_agent"}')
            return

        if path == "/api/clear":
            result = self._perform_full_data_wipe()
            self._send_json(result)
            return

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
            self.send_header("Pragma", "no-cache")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
            return

        if path == "/api/profile":
            pm = ProfileManager()
            prof = pm.load_profile()
            data = prof.model_dump() if prof else {}
            self._send_json(data)
            return

        if path in ("/api/jobs", "/api/applications"):
            conn = init_db()
            cursor = conn.cursor()
            # Fast backfill for any existing unscored jobs (strictly unscored only)
            try:
                cursor.execute(
                    """
                    SELECT j.id, j.title, j.company, j.location, j.raw_jd
                    FROM jobs j
                    WHERE j.id NOT IN (SELECT job_id FROM job_matches)
                    LIMIT 200
                    """
                )
                unscored = cursor.fetchall()
                if unscored:
                    from src.matching.scorer import calculate_match_score
                    pm = ProfileManager()
                    profile = pm.load_profile()
                    for j_id, title, comp, loc, raw_jd in unscored:
                        regex_skills = JDAgent._regex_preextract_skills(raw_jd or "")
                        req = ParsedJDRequirements(
                            title=title or "Software Engineer",
                            company=comp or "Company",
                            location=loc or "Bengaluru",
                            required_skills=regex_skills,
                            min_years_experience=1,
                            keywords=regex_skills
                        )
                        eval_res = calculate_match_score(profile, req)
                        new_status = "QUALIFIED" if eval_res.overall_score >= 60 else "SKIPPED"
                        breakdown_json = json.dumps(eval_res.score_breakdown.model_dump())
                        cursor.execute(
                            """
                            INSERT OR REPLACE INTO job_matches (job_id, overall_score, decision, breakdown_json)
                            VALUES (?, ?, ?, ?)
                            """,
                            (j_id, eval_res.overall_score, eval_res.decision, breakdown_json)
                        )
                        cursor.execute(
                            "UPDATE applications SET status = ? WHERE job_id = ? AND status = 'DISCOVERED'",
                            (new_status, j_id)
                        )
                    conn.commit()
            except Exception as bfe:
                logger.debug(f"Backfill unscored jobs notice: {bfe}")

            cursor.execute(
                """
                SELECT j.id, j.company, j.title, j.source, j.url, a.status,
                       COALESCE(MAX(jm.overall_score), 0) AS overall_score,
                       COALESCE(MAX(jm.decision), 'SKIP') AS decision,
                       rv.file_path, j.location
                FROM jobs j
                JOIN applications a ON j.id = a.job_id
                LEFT JOIN job_matches jm ON j.id = jm.job_id
                LEFT JOIN resume_versions rv ON a.resume_version_id = rv.id
                GROUP BY j.id
                ORDER BY overall_score DESC, j.id DESC
                """
            )
            rows = cursor.fetchall()
            history = []
            for r in rows:
                history.append({
                    "job_id": r[0],
                    "company": r[1],
                    "title": r[2],
                    "source": r[3],
                    "url": r[4],
                    "status": r[5],
                    "match_score": r[6],
                    "decision": r[7],
                    "tailored_resume_path": r[8],
                    "location": r[9] if len(r) > 9 else "Bengaluru"
                })
            conn.close()
            self._send_json(history)
            return

        if path == "/api/events":
            params = urllib.parse.parse_qs(parsed.query)
            job_id = int(params.get("job_id", [0])[0])
            audit = AuditManager()
            events = audit.get_application_events(job_id) if job_id else []
            self._send_json(events)
            return

        if path == "/api/logs":
            # Server-Sent Events endpoint — keeps connection alive and streams log lines
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "keep-alive")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            # Create a per-client queue and register it
            client_q: queue.Queue = queue.Queue(maxsize=200)
            with _sse_lock:
                _sse_clients.append(client_q)
            try:
                # Send a keepalive comment every 10s to prevent cloud proxy idle disconnects
                while True:
                    try:
                        data = client_q.get(timeout=10)
                        self.wfile.write(data.encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # Send SSE keep-alive comment
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass
            except Exception as e:
                logger.debug(f"SSE client disconnected: {e}")
            finally:
                with _sse_lock:
                    if client_q in _sse_clients:
                        _sse_clients.remove(client_q)
            return

        if path == "/api/view-resume":
            params = urllib.parse.parse_qs(parsed.query)
            file_param = params.get("file", [""])[0]
            if file_param:
                file_path = Path(file_param)
                if file_path.exists() and file_path.suffix.lower() == ".pdf":
                    try:
                        with open(file_path, "rb") as f:
                            content = f.read()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/pdf")
                        self.send_header("Content-Disposition", f"inline; filename=\"{file_path.name}\"")
                        self.send_header("Content-Length", str(len(content)))
                        self.end_headers()
                        self.wfile.write(content)
                        return
                    except Exception as e:
                        logger.error(f"Error serving PDF {file_path}: {e}")
        if path == "/api/outreach":
            params = urllib.parse.parse_qs(parsed.query)
            job_id_param = params.get("job_id", [""])[0]
            if job_id_param and job_id_param.isdigit():
                j_id = int(job_id_param)
                conn = init_db()
                try:
                    c = conn.cursor()
                    c.execute("SELECT company, title, analyzed_requirements FROM jobs WHERE id = ?", (j_id,))
                    row = c.fetchone()
                    if row:
                        comp = row["company"]
                        tit = row["title"]
                        req_json = row["analyzed_requirements"]
                        reqs = None
                        if req_json:
                            try:
                                reqs = ParsedJDRequirements(**json.loads(req_json))
                            except Exception:
                                pass
                        pm = ProfileManager()
                        prof = pm.load_profile()
                        from src.ai.outreach import generate_outreach_messages
                        outreach_data = generate_outreach_messages(prof, comp, tit, reqs)
                        self._send_json({"status": "SUCCESS", "data": outreach_data})
                        return
                finally:
                    conn.close()
            self._send_json({"status": "ERROR", "error": "Job not found"})
            return

        if path == "/api/ats-scorecard":
            params = urllib.parse.parse_qs(parsed.query)
            job_id_param = params.get("job_id", [""])[0]
            if job_id_param and job_id_param.isdigit():
                j_id = int(job_id_param)
                conn = init_db()
                try:
                    c = conn.cursor()
                    c.execute("SELECT j.company, j.title, j.analyzed_requirements, jm.overall_score FROM jobs j LEFT JOIN job_matches jm ON j.id = jm.job_id WHERE j.id = ?", (j_id,))
                    row = c.fetchone()
                    if row:
                        comp = row["company"]
                        tit = row["title"]
                        req_json = row["analyzed_requirements"]
                        score = row["overall_score"] or 75
                        reqs = None
                        if req_json:
                            try:
                                reqs = ParsedJDRequirements(**json.loads(req_json))
                            except Exception:
                                pass
                        pm = ProfileManager()
                        prof = pm.load_profile()
                        cand_skills = set(s.lower() for s in (prof.skills if prof else []))
                        if prof:
                            for exp in prof.experience:
                                cand_skills.update(s.lower() for s in exp.verified_skills)
                        
                        req_skills = reqs.required_skills if (reqs and reqs.required_skills) else ["Python", "FastAPI", "PostgreSQL", "Docker", "Playwright"]
                        matched = [s for s in req_skills if s.lower() in cand_skills or any(s.lower() in cs for cs in cand_skills)]
                        injected = [s for s in req_skills if s not in matched]
                        grade = "A+ (Excellent)" if score >= 85 else "A (Strong Match)" if score >= 75 else "B+ (Good Fit)"
                        
                        self._send_json({
                            "status": "SUCCESS",
                            "job_id": j_id,
                            "company": comp,
                            "title": tit,
                            "ats_score": score,
                            "ats_grade": grade,
                            "matched_skills": matched,
                            "injected_keywords": injected,
                            "total_required": len(req_skills)
                        })
                        return
                finally:
                    conn.close()
            self._send_json({"status": "ERROR", "error": "Job not found"})
            return

        if path == "/api/cover-letter":
            params = urllib.parse.parse_qs(parsed.query)
            job_id_param = params.get("job_id", [""])[0]
            if job_id_param and job_id_param.isdigit():
                j_id = int(job_id_param)
                conn = init_db()
                try:
                    c = conn.cursor()
                    c.execute("SELECT company, title, analyzed_requirements FROM jobs WHERE id = ?", (j_id,))
                    row = c.fetchone()
                    if row:
                        comp = row["company"]
                        tit = row["title"]
                        req_json = row["analyzed_requirements"]
                        reqs = None
                        if req_json:
                            try:
                                reqs = ParsedJDRequirements(**json.loads(req_json))
                            except Exception:
                                pass
                        pm = ProfileManager()
                        prof = pm.load_profile()
                        from src.resume.cover_letter import generate_cover_letter_text, generate_cover_letter_pdf
                        cl_text = generate_cover_letter_text(prof, comp, tit, reqs)
                        safe_comp = re.sub(r'[^a-zA-Z0-9]', '_', comp)
                        pdf_path = Path("data") / "cover_letters" / f"cover_letter_job{j_id}_{safe_comp}.pdf"
                        generate_cover_letter_pdf(prof, comp, tit, pdf_path, reqs)
                        self._send_json({
                            "status": "SUCCESS",
                            "text": cl_text,
                            "company": comp,
                            "title": tit,
                            "pdf_url": f"/api/view-resume?file={urllib.parse.quote(str(pdf_path))}"
                        })
                        return
                finally:
                    conn.close()
            self._send_json({"status": "ERROR", "error": "Job not found"})
            return

        if path == "/api/interview-prep":
            params = urllib.parse.parse_qs(parsed.query)
            job_id_param = params.get("job_id", [""])[0]
            if job_id_param and job_id_param.isdigit():
                j_id = int(job_id_param)
                conn = init_db()
                try:
                    c = conn.cursor()
                    c.execute("SELECT company, title, analyzed_requirements FROM jobs WHERE id = ?", (j_id,))
                    row = c.fetchone()
                    if row:
                        comp = row["company"]
                        tit = row["title"]
                        req_json = row["analyzed_requirements"]
                        reqs = None
                        if req_json:
                            try:
                                reqs = ParsedJDRequirements(**json.loads(req_json))
                            except Exception:
                                pass
                        pm = ProfileManager()
                        prof = pm.load_profile()
                        from src.ai.interview_prep import generate_interview_prep
                        prep_data = generate_interview_prep(prof, comp, tit, reqs)
                        self._send_json({"status": "SUCCESS", **prep_data})
                        return
                finally:
                    conn.close()
            self._send_json({"status": "ERROR", "error": "Job not found"})
            return

        if path == "/api/scheduler":
            from src.automation.scheduler import scheduler
            self._send_json(scheduler.get_status())
            return

        if path == "/api/followups":
            from src.outreach.followup_agent import followup_manager
            followups = followup_manager.get_pending_followups()
            self._send_json({"status": "SUCCESS", "followups": followups})
            return

        if path == "/api/notifications":
            from config import settings
            self._send_json({
                "tg_token": getattr(settings, "TELEGRAM_BOT_TOKEN", ""),
                "tg_chat_id": getattr(settings, "TELEGRAM_CHAT_ID", ""),
                "discord_webhook": getattr(settings, "DISCORD_WEBHOOK_URL", ""),
                "smtp_user": getattr(settings, "SMTP_USER", ""),
                "smtp_password": getattr(settings, "SMTP_PASSWORD", ""),
                "smtp_from_name": getattr(settings, "SMTP_FROM_NAME", "Sasi Kumar Reddy Chintala"),
                "sheets_webhook": getattr(settings, "GOOGLE_SHEETS_WEBHOOK_URL", ""),
                "notion_key": getattr(settings, "NOTION_API_KEY", ""),
                "notion_db": getattr(settings, "NOTION_DATABASE_ID", "")
            })
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/sync/all":
            from src.sync.tracker_sync import tracker_sync
            res = tracker_sync.sync_all_qualified()
            self._send_json({"status": "SUCCESS", "message": res.get("message"), "count": res.get("synced_count", 0)})
            return

        if path == "/api/email/send":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            payload = json.loads(body) if body else {}

            job_id = payload.get("job_id")
            to_email = payload.get("to_email", "").strip()
            subject = payload.get("subject", "").strip()
            email_body = payload.get("body", "").strip()
            attach_resume = payload.get("attach_resume", True)
            attach_cover = payload.get("attach_cover", True)

            resume_path = None
            if attach_resume and job_id:
                from src.agents.resume_agent import ResumeTailorAgent
                try:
                    agent = ResumeTailorAgent()
                    resume_path = agent.tailor_resume_for_job(int(job_id))
                except Exception as e:
                    logger.debug(f"Resume tailor notice: {e}")

            cover_path = None
            if attach_cover and job_id:
                from src.resume.cover_letter import generate_cover_letter_pdf
                from src.ai.schemas import ParsedJDRequirements
                conn = init_db()
                try:
                    c = conn.cursor()
                    c.execute("SELECT company, title, analyzed_requirements FROM jobs WHERE id = ?", (job_id,))
                    row = c.fetchone()
                    if row:
                        comp = row["company"]
                        tit = row["title"]
                        req_json = row["analyzed_requirements"]
                        reqs = ParsedJDRequirements(**json.loads(req_json)) if req_json else None
                        pm = ProfileManager()
                        prof = pm.load_profile()
                        cover_path = generate_cover_letter_pdf(prof, comp, tit, reqs)
                finally:
                    conn.close()

            from src.outreach.email_dispatcher import email_dispatcher
            res = email_dispatcher.send_cold_email(
                to_email=to_email,
                subject=subject,
                body_text=email_body,
                resume_pdf_path=Path(resume_path) if resume_path else None,
                cover_letter_pdf_path=Path(cover_path) if cover_path else None,
                job_id=int(job_id) if job_id else None
            )

            if res.get("success"):
                self._send_json({"status": "SUCCESS", "message": res.get("message")})
            else:
                self._send_json({"status": "FAILED", "error": res.get("error")})
            return

        if path == "/api/notifications":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            payload = json.loads(body) if body else {}
            from config import BASE_DIR, settings as app_settings
            app_settings.TELEGRAM_BOT_TOKEN = payload.get("tg_token", "")
            app_settings.TELEGRAM_CHAT_ID = payload.get("tg_chat_id", "")
            app_settings.DISCORD_WEBHOOK_URL = payload.get("discord_webhook", "")
            app_settings.SMTP_USER = payload.get("smtp_user", "")
            app_settings.SMTP_PASSWORD = payload.get("smtp_password", "")
            app_settings.SMTP_FROM_NAME = payload.get("smtp_from_name", "Sasi Kumar Reddy Chintala")
            app_settings.GOOGLE_SHEETS_WEBHOOK_URL = payload.get("sheets_webhook", "")
            app_settings.NOTION_API_KEY = payload.get("notion_key", "")
            app_settings.NOTION_DATABASE_ID = payload.get("notion_db", "")

            try:
                env_file = BASE_DIR / ".env"
                env_lines = []
                if env_file.exists():
                    with open(env_file, "r", encoding="utf-8") as f:
                        env_lines = f.readlines()
                
                keys_to_set = {
                    "TELEGRAM_BOT_TOKEN": app_settings.TELEGRAM_BOT_TOKEN,
                    "TELEGRAM_CHAT_ID": app_settings.TELEGRAM_CHAT_ID,
                    "DISCORD_WEBHOOK_URL": app_settings.DISCORD_WEBHOOK_URL,
                    "SMTP_USER": app_settings.SMTP_USER,
                    "SMTP_PASSWORD": app_settings.SMTP_PASSWORD,
                    "SMTP_FROM_NAME": app_settings.SMTP_FROM_NAME,
                    "GOOGLE_SHEETS_WEBHOOK_URL": app_settings.GOOGLE_SHEETS_WEBHOOK_URL,
                    "NOTION_API_KEY": app_settings.NOTION_API_KEY,
                    "NOTION_DATABASE_ID": app_settings.NOTION_DATABASE_ID
                }
                new_lines = []
                found_keys = set()
                for line in env_lines:
                    k = line.split("=")[0].strip() if "=" in line else ""
                    if k in keys_to_set:
                        new_lines.append(f"{k}={keys_to_set[k]}\n")
                        found_keys.add(k)
                    else:
                        new_lines.append(line)
                for k, v in keys_to_set.items():
                    if k not in found_keys:
                        new_lines.append(f"{k}={v}\n")
                with open(env_file, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                logger.info(f" Saved Alerts, SMTP & Tracker Credentials! Sheets: {'Active' if settings.GOOGLE_SHEETS_WEBHOOK_URL else 'Inactive'} | Notion: {'Active' if settings.NOTION_DATABASE_ID else 'Inactive'}")
            except Exception as e:
                logger.warning(f"Could not persist .env: {e}")

            self._send_json({"status": "SUCCESS"})
            return

        if path == "/api/notifications/test":
            from src.notifications.notifier import NotificationManager
            res = NotificationManager.send_test_notification()
            logger.info(f" Dispatched Test Notification: {res}")
            self._send_json({"status": "SUCCESS", "results": res})
            return

        if path == "/api/scheduler/toggle":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            payload = json.loads(body) if body else {}
            from src.automation.scheduler import scheduler
            if payload.get("schedule_time"):
                scheduler.schedule_time = payload.get("schedule_time")
            if scheduler.enabled:
                scheduler.stop()
            else:
                scheduler.start()
            self._send_json(scheduler.get_status())
            return

        if path == "/api/scheduler/update-time":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            payload = json.loads(body) if body else {}
            from src.automation.scheduler import scheduler
            if payload.get("schedule_time"):
                scheduler.schedule_time = payload.get("schedule_time")
            self._send_json(scheduler.get_status())
            return

        if path == "/api/scheduler/run-now":
            from src.automation.scheduler import scheduler
            def _bg_run():
                scheduler.run_now()
            threading.Thread(target=_bg_run, daemon=True).start()
            self._send_json({"status": "STARTED"})
            return

        if path == "/api/search-and-match":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            payload = json.loads(body) if body else {}

            query = payload.get("query", "Python Developer")
            location = payload.get("location", "Bengaluru")
            time_range = payload.get("time_range", "3d")

            def _worker():
                try:
                    from src.jobs.finder import JobFinder
                    from src.agents.jd_agent import JDAgent
                    from src.agents.match_agent import MatchAgent
                    from src.agents.resume_agent import ResumeTailorAgent

                    logger.info(f" Starting 1-Click Search & Score for '{query}' in '{location}' ({time_range})...")
                    finder = JobFinder.create_multi_source_finder()
                    discovered = finder.discover_jobs(query=query, location=location, time_range=time_range)
                    logger.info(f" Discovery complete: {len(discovered)} new jobs stored.")

                    jd_agent = JDAgent()
                    analyzed = jd_agent.analyze_all_pending_jobs(limit=30)
                    logger.info(f" Analyzed {len(analyzed)} pending JDs.")

                    match_agent = MatchAgent()
                    evals = match_agent.evaluate_all_pending_jobs()
                    logger.info(f" Match evaluation complete: {len(evals)} jobs evaluated.")

                    tailor_agent = ResumeTailorAgent()
                    tailored = tailor_agent.tailor_all_pending_jobs(limit=10)
                    logger.info(f" Resume tailoring complete: {len(tailored)} tailored PDF resumes generated.")
                    import gc
                    gc.collect()
                except Exception as e:
                    logger.error(f"Search & Score background error: {e}")

            t = threading.Thread(target=_worker, daemon=True)
            t.start()

            self._send_json({"status": "STARTED"})
            return

        if path == "/api/discover":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            payload = json.loads(body) if body else {}

            query = payload.get("query", "Python Developer")
            location = payload.get("location", "Bengaluru")
            time_range = payload.get("time_range", "3d")

            finder = JobFinder.create_multi_source_finder()
            discovered = finder.discover_jobs(query=query, location=location, time_range=time_range)
            self._send_json({"status": "SUCCESS", "count": len(discovered)})
            return

        if path == "/api/scout-software":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            payload = json.loads(body) if body else {}
            location = payload.get("location", "Bengaluru")
            time_range = payload.get("time_range", "3d")

            def _swe_bg_worker():
                try:
                    from src.jobs.finder import JobFinder
                    from src.agents.jd_agent import JDAgent
                    from src.agents.match_agent import MatchAgent
                    from src.agents.resume_agent import ResumeTailorAgent

                    logger.info(f" Starting Software Engineer & Developer scout in '{location}' ({time_range})...")
                    finder = JobFinder.create_multi_source_finder()
                    discovered = finder.discover_software_engineer_jobs(location=location, time_range=time_range)
                    logger.info(f" Discovered {len(discovered)} Software Engineer & Developer jobs.")

                    jd_agent = JDAgent()
                    analyzed = jd_agent.analyze_all_pending_jobs(limit=30)

                    match_agent = MatchAgent()
                    evals = match_agent.evaluate_all_pending_jobs()
                    logger.info(f" Evaluated {len(evals)} jobs against candidate resume.")

                    tailor_agent = ResumeTailorAgent()
                    tailor_agent.tailor_all_pending_jobs(limit=10)
                    import gc
                    gc.collect()
                except Exception as e:
                    logger.error(f"Software scout background error: {e}")

            threading.Thread(target=_swe_bg_worker, daemon=True).start()
            self._send_json({"status": "STARTED"})
            return

        if path == "/api/run-agent":
            def _apply_worker():
                try:
                    logger.info(" Starting Automated Application Pipeline in background...")
                    orch = ApplicationOrchestrator()
                    orch.run_pipeline()
                except Exception as e:
                    logger.error(f"Auto-Apply background error: {e}")

            t = threading.Thread(target=_apply_worker, daemon=True)
            t.start()
            self._send_json({"status": "STARTED"})
            return

        if path == "/api/upload-resume":
            import base64
            from config import settings
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            payload = json.loads(body) if body else {}

            filename = payload.get("filename", "uploaded_resume.pdf")
            b64_data = payload.get("content_base64", "")
            
            if not b64_data:
                self._send_json({"status": "ERROR", "error": "No file content provided"})
                return

            try:
                file_bytes = base64.b64decode(b64_data)
                save_path = settings.MASTER_RESUME_PATH.parent / filename
                with open(save_path, "wb") as f:
                    f.write(file_bytes)

                from src.resume.parser import parse_resume_to_candidate_profile
                profile = parse_resume_to_candidate_profile(save_path)
                pm = ProfileManager()
                pm.save_profile(profile)
                
                self._send_json({"status": "SUCCESS", "profile": profile.model_dump()})
            except Exception as e:
                logger.error(f"UI Resume upload failed: {e}")
                self._send_json({"status": "ERROR", "error": str(e)})
            return

        if path == "/api/tailor-job":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            payload = json.loads(body) if body else {}
            job_id = payload.get("job_id")
            if not job_id:
                params = urllib.parse.parse_qs(parsed.query)
                job_id = int(params.get("job_id", [0])[0])

            if not job_id:
                self._send_json({"status": "ERROR", "message": "job_id is required"})
                return

            try:
                from src.agents.resume_agent import ResumeTailorAgent
                tailor_agent = ResumeTailorAgent()
                pdf_path = tailor_agent.tailor_resume_for_job(job_id)
                self._send_json({"status": "SUCCESS", "job_id": job_id, "tailored_resume_path": pdf_path})
            except Exception as te:
                logger.error(f"UI Tailor error for job #{job_id}: {te}")
                self._send_json({"status": "ERROR", "message": str(te)})
            return

        if path == "/api/apply-job":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            payload = json.loads(body) if body else {}
            job_id = payload.get("job_id")
            if not job_id:
                params = urllib.parse.parse_qs(parsed.query)
                job_id = int(params.get("job_id", [0])[0])

            if not job_id:
                self._send_json({"status": "ERROR", "message": "job_id is required"})
                return

            def _apply_single():
                try:
                    conn = init_db()
                    c = conn.cursor()
                    c.execute("SELECT url FROM jobs WHERE id = ?", (job_id,))
                    row = c.fetchone()
                    conn.close()
                    if row and row[0]:
                        from src.automation.pilot import PilotRunner
                        runner = PilotRunner()
                        runner.run_pilot_on_url(row[0], is_live_submission=False)
                except Exception as ae:
                    logger.error(f"Single apply error for job #{job_id}: {ae}")

            threading.Thread(target=_apply_single, daemon=True).start()
            self._send_json({"status": "STARTED", "job_id": job_id})
            return

        if path == "/api/db-status":
            db_type = getattr(settings, "DATABASE_TYPE", "sqlite")
            db_url = getattr(settings, "DATABASE_URL", "") or ""
            is_postgres = db_type == "postgres" and bool(db_url.strip())
            status_data = {
                "engine": "PostgreSQL (Cloud/Supabase)" if is_postgres else "SQLite (Local/WAL)",
                "persistence": "Permanent Cloud Storage" if is_postgres else "Local Disk",
                "connected": False,
                "job_count": 0,
                "match_count": 0,
                "qualified_count": 0
            }
            try:
                conn = init_db()
                c = conn.cursor()
                c.execute("SELECT COUNT(*) FROM jobs")
                status_data["job_count"] = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM job_matches")
                status_data["match_count"] = c.fetchone()[0]
                c.execute("SELECT COUNT(*) FROM applications WHERE status = 'QUALIFIED'")
                status_data["qualified_count"] = c.fetchone()[0]
                conn.close()
                status_data["connected"] = True
            except Exception as e:
                status_data["error"] = str(e)
            self._send_json(status_data)
            return

        if path == "/api/clear":
            result = self._perform_full_data_wipe()
            self._send_json(result)
            return

        self.send_response(404)
        self.end_headers()

    def _perform_full_data_wipe(self):
        """Wipes all jobs, match evaluations, application history, and tailored PDF resume files."""
        deleted_resumes_count = 0
        try:
            # 1. Purge physical tailored PDF resumes on disk
            tailored_dir = settings.TAILORED_RESUMES_DIR
            if tailored_dir.exists():
                for f in tailored_dir.glob("*"):
                    try:
                        if f.is_file():
                            f.unlink()
                            deleted_resumes_count += 1
                    except Exception:
                        pass

            # 2. Purge database records
            conn = init_db()
            with conn:
                conn.execute("DELETE FROM application_events")
                conn.execute("DELETE FROM applications")
                conn.execute("DELETE FROM job_matches")
                conn.execute("DELETE FROM resume_versions")
                conn.execute("DELETE FROM jobs")
                conn.execute("DELETE FROM agent_runs")
                try:
                    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('jobs', 'job_matches', 'applications', 'resume_versions', 'application_events', 'agent_runs')")
                except Exception:
                    pass
            conn.close()
            logger.info(f"[CLEAN SLATE] Wiped all database records and {deleted_resumes_count} tailored PDF files.")
            return {
                "status": "CLEARED",
                "message": f"Wiped all jobs, evaluations, and {deleted_resumes_count} tailored PDF resumes!",
                "deleted_resumes": deleted_resumes_count
            }
        except Exception as e:
            logger.error(f"Failed to wipe data: {e}")
            return {"status": "ERROR", "error": str(e)}

    def _send_json(self, data):
        try:
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
            pass

    def log_message(self, format, *args):
        pass

def run_dashboard_server(host: str = "0.0.0.0", port: int = 8000):
    """Starts local HTTP dashboard server (threaded for SSE support and mobile accessible)."""
    class ThreadedHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True
        def handle_error(self, request, client_address):
            # Suppress normal client disconnection errors silently
            pass

    server = ThreadedHTTPServer((host, port), AgentDashboardHandler)
    logger.info("=" * 60)
    logger.info(f"[bold green] Local AI Job Agent Dashboard Running at: http://localhost:{port}[/bold green]")
    logger.info(f"[bold cyan] Mobile Phone Access (Same Wi-Fi): http://192.168.31.87:{port}[/bold cyan]")
    logger.info("=" * 60)

    # Start 2-Way Interactive Telegram Bot Daemon if configured
    try:
        from src.notifications.telegram_bot import telegram_bot
        if telegram_bot.is_configured:
            telegram_bot.start()
            logger.info("[bold cyan]📱 2-Way Interactive Telegram Assistant is active & listening to your phone![/bold cyan]")
    except Exception as e:
        logger.debug(f"Telegram Bot start notice: {e}")

    # Start 24/7 Autonomous Job Scheduler Daemon
    try:
        from src.automation.scheduler import scheduler
        if getattr(settings, "AUTO_SCOUT_ENABLED", True):
            scheduler.schedule_time = getattr(settings, "AUTO_SCOUT_SCHEDULE", "08:00")
            scheduler.start()
            logger.info(f"[bold cyan]⏰ 24/7 Autonomous Job Scheduler active! Runs daily at {scheduler.schedule_time}[/bold cyan]")
    except Exception as se:
        logger.debug(f"Scheduler auto-start notice: {se}")

    # Auto-seed / Auto-discover on startup if database is fresh
    def _startup_scout():
        try:
            conn = init_db()
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM jobs")
            count = c.fetchone()[0]
            conn.close()
            if count == 0:
                logger.info("[STARTUP] Fresh database detected. Auto-discovering 0-2 Yrs jobs in background...")
                from src.jobs.finder import JobFinder
                from src.agents.jd_agent import JDAgent
                from src.agents.match_agent import MatchAgent
                from src.agents.resume_agent import ResumeTailorAgent

                finder = JobFinder.create_multi_source_finder()
                discovered = finder.discover_jobs(query="Junior Python Developer 0-2 years", location="Bengaluru", time_range="3d")
                jd_agent = JDAgent()
                jd_agent.analyze_all_pending_jobs(limit=50)
                match_agent = MatchAgent()
                match_agent.evaluate_all_pending_jobs()
                tailor_agent = ResumeTailorAgent()
                tailor_agent.tailor_all_pending_jobs()
                logger.info(f"[STARTUP] Initial auto-scout complete: {len(discovered)} jobs ready on dashboard!")
        except Exception as e:
            logger.debug(f"Startup scout notice: {e}")

    threading.Thread(target=_startup_scout, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard server stopped.")
    finally:
        server.server_close()
