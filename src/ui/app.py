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


DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Personal AI Job Application Agent</title>
    <style>
        :root {
            --bg-color: #0b1329;
            --card-bg: #131f37;
            --card-border: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --success: #22c55e;
            --warning: #eab308;
            --danger: #ef4444;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 24px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--card-border);
            padding-bottom: 16px;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 12px;
        }
        h1 { margin: 0; font-size: 24px; color: var(--accent); }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 16px;
        }
        .stat-label { font-size: 13px; color: var(--text-muted); text-transform: uppercase; }
        .stat-val { font-size: 28px; font-weight: bold; margin-top: 4px; }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 24px;
        }
        .search-bar {
            display: flex;
            gap: 12px;
            margin-top: 12px;
            flex-wrap: wrap;
        }
        .input-box {
            background: #0f172a;
            border: 1px solid var(--card-border);
            color: #fff;
            padding: 10px 14px;
            border-radius: 6px;
            font-size: 14px;
            flex: 1;
            min-width: 180px;
        }
        .btn {
            background: var(--accent);
            color: #0f172a;
            font-weight: 600;
            border: none;
            padding: 10px 18px;
            border-radius: 6px;
            cursor: pointer;
            transition: opacity 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }
        .btn-green {
            background: var(--success);
            color: #0b1329;
        }
        .btn-outline {
            background: transparent;
            color: var(--text-muted);
            border: 1px solid var(--card-border);
        }
        .btn-outline:hover { color: #fff; border-color: var(--text-muted); }
        .btn:hover { opacity: 0.9; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
        }
        th, td {
            text-align: left;
            padding: 12px;
            border-bottom: 1px solid var(--card-border);
            font-size: 14px;
        }
        th { color: var(--text-muted); font-size: 12px; text-transform: uppercase; }
        .badge {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }
        .badge-DISCOVERED { background: rgba(148, 163, 184, 0.2); color: var(--text-muted); }
        .badge-ANALYZED { background: rgba(168, 85, 247, 0.2); color: #c084fc; }
        .badge-QUALIFIED { background: rgba(56, 189, 248, 0.2); color: var(--accent); }
        .badge-RESUME_READY { background: rgba(234, 179, 8, 0.2); color: var(--warning); }
        .badge-READY_TO_SUBMIT { background: rgba(34, 197, 94, 0.2); color: var(--success); }
        .badge-SUBMITTED { background: rgba(34, 197, 94, 0.4); color: #fff; }
        .badge-SKIPPED { background: rgba(239, 68, 68, 0.2); color: var(--danger); }
        .link { color: var(--accent); text-decoration: none; }
        .link:hover { text-decoration: underline; }
        .score-high { color: var(--success); font-weight: bold; font-size: 15px; }
        .score-med { color: var(--warning); font-weight: bold; }
        .score-low { color: var(--text-muted); }
        /* Live Activity Log */
        .log-panel {
            background: #060d1f;
            border: 1px solid #1e293b;
            border-radius: 8px;
            padding: 14px 16px;
            margin-bottom: 24px;
            font-family: 'Courier New', Courier, monospace;
            font-size: 12.5px;
            min-height: 120px;
            max-height: 220px;
            overflow-y: auto;
            scroll-behavior: smooth;
        }
        .log-panel-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .log-line { padding: 2px 0; line-height: 1.55; word-break: break-word; }
        .log-dot {
            display: inline-block;
            width: 8px; height: 8px;
            border-radius: 50%;
            background: var(--success);
            margin-right: 6px;
            animation: pulse 1.4s ease-in-out infinite;
        }
        /* Modal Styles */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background: rgba(0, 0, 0, 0.75);
            backdrop-filter: blur(4px);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-overlay.open { display: flex; }
        .modal-box {
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            width: 90%;
            max-width: 650px;
            max-height: 85vh;
            overflow-y: auto;
            padding: 24px;
            box-shadow: 0 20px 30px rgba(0,0,0,0.5);
            position: relative;
        }
        .modal-tabs {
            display: flex;
            gap: 8px;
            margin: 16px 0;
            border-bottom: 1px solid var(--border);
            padding-bottom: 8px;
        }
        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 13px;
            padding: 6px 12px;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .tab-btn.active {
            background: rgba(56, 189, 248, 0.15);
            color: var(--accent);
        }
        .outreach-content-box {
            background: #090d16;
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 14px;
            font-size: 13px;
            line-height: 1.6;
            color: #cbd5e1;
            white-space: pre-wrap;
            font-family: inherit;
            margin-bottom: 12px;
            min-height: 120px;
        }
        .copy-btn {
            background: var(--accent);
            color: #000;
            font-weight: 700;
            border: none;
            padding: 7px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: background 0.2s;
        }
        .copy-btn:hover { background: #7dd3fc; }
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
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            z-index: 2000;
        }
    </style>
</head>
<body>
    <!-- Outreach Modal -->
    <div id="outreach-modal" class="modal-overlay" onclick="if(event.target===this) closeOutreachModal()">
        <div class="modal-box">
            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                <div>
                    <h2 id="modal-company-title" style="margin: 0; font-size: 18px; color: var(--accent);">Recruiter & Hiring Manager Outreach</h2>
                    <p id="modal-role-subtitle" style="margin: 4px 0 0 0; color: var(--text-muted); font-size: 13px;">Personalized 1-click cold messages</p>
                </div>
                <button onclick="closeOutreachModal()" style="background:transparent;border:none;color:var(--text-muted);font-size:20px;cursor:pointer;">&times;</button>
            </div>

            <div class="modal-tabs">
                <button id="tab-li" class="tab-btn active" onclick="switchOutreachTab('li')">💼 LinkedIn Note (<300 chars)</button>
                <button id="tab-email" class="tab-btn" onclick="switchOutreachTab('email')">✉️ Cold Email (Hiring Mgr)</button>
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
                <button class="copy-btn" onclick="copyModalText('text-li')">📋 Copy LinkedIn Note</button>
            </div>

            <div id="view-email" style="display:none;">
                <div style="margin-bottom:8px;">
                    <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">Recipient Email (Hiring Lead / Recruiter):</div>
                    <input id="text-email-to" type="email" class="input-box" placeholder="e.g. careers@company.com or engineering-lead@company.com" style="margin:0 0 8px 0;">
                    
                    <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">Subject:</div>
                    <div style="display:flex; gap:8px; margin-bottom:8px;">
                        <input id="text-email-sub" type="text" class="input-box" style="margin:0; flex:1;">
                        <button class="copy-btn" onclick="copyInputVal('text-email-sub')">Copy</button>
                    </div>
                </div>
                <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">Email Body:</div>
                <textarea id="text-email-body" class="outreach-content-box" style="width:100%; min-height:140px; resize:vertical; font-family:inherit; font-size:12px; line-height:1.5;"></textarea>

                <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; margin:10px 0; gap:8px;">
                    <div style="display:flex; gap:16px; font-size:12px; color:var(--text-muted);">
                        <label style="display:flex; align-items:center; gap:6px; cursor:pointer;"><input type="checkbox" id="email-attach-resume" checked> 📄 Attach Tailored Resume PDF</label>
                        <label style="display:flex; align-items:center; gap:6px; cursor:pointer;"><input type="checkbox" id="email-attach-cover" checked> 📝 Attach Cover Letter PDF</label>
                    </div>
                    <div style="display:flex; gap:8px;">
                        <button class="copy-btn" onclick="copyEmailBodyFromTextarea()">📋 Copy Text</button>
                        <button class="btn btn-green" style="font-size:12px; padding:6px 14px; display:inline-flex; align-items:center; gap:6px;" onclick="sendDirectColdEmail()">🚀 Send Cold Email Now</button>
                    </div>
                </div>
                <div id="email-dispatch-status" style="display:none; padding:8px 12px; border-radius:6px; font-size:12px; margin-top:8px;"></div>
            </div>

            <div id="view-inmail" style="display:none;">
                <div style="font-size:12px; color:var(--text-muted); margin-bottom:4px;">InMail Message:</div>
                <div id="text-inmail" class="outreach-content-box">Loading...</div>
                <button class="copy-btn" onclick="copyModalText('text-inmail')">📋 Copy InMail</button>
            </div>

            <div id="view-cl" style="display:none;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-size:12px; color:var(--text-muted);">Tailored 2-Paragraph Cover Letter:</span>
                    <a id="cl-pdf-link" href="#" target="_blank" class="copy-btn" style="background:#f59e0b; color:#000; text-decoration:none; padding:5px 12px; font-size:11px;">📄 View Cover Letter PDF ↗</a>
                </div>
                <div id="text-cl" class="outreach-content-box" style="min-height:160px;">Loading...</div>
                <button class="copy-btn" onclick="copyModalText('text-cl')">📋 Copy Cover Letter Text</button>
            </div>

            <div id="view-prep" style="display:none;">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-size:12px; color:var(--text-muted);">AI Predicted Technical Questions & STAR Talking Points:</span>
                    <button class="copy-btn" onclick="copyModalText('text-prep')">📋 Copy All Prep Notes</button>
                </div>
                <div id="text-prep" class="outreach-content-box" style="min-height:220px; font-size:12px;">Loading...</div>
            </div>
        </div>
    </div>

    <!-- Notification & SMTP Setup Modal -->
    <div id="notif-modal" class="modal-overlay" onclick="if(event.target===this) closeNotifModal()">
        <div class="modal-box" style="max-width: 580px;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px;">
                <div>
                    <h2 style="margin: 0; font-size: 18px; color: var(--accent);">⚙️ Alerts & Direct Email Setup</h2>
                    <p style="margin: 4px 0 0 0; color: var(--text-muted); font-size: 13px;">Configure Telegram mobile alerts, Discord, and 1-Click Gmail SMTP cold emailing</p>
                </div>
                <button onclick="closeNotifModal()" style="background:transparent;border:none;color:var(--text-muted);font-size:20px;cursor:pointer;">&times;</button>
            </div>

            <div style="display:flex; flex-direction:column; gap:12px;">
                <div style="background:#090d16; padding:12px; border-radius:8px; border:1px solid var(--border);">
                    <h4 style="margin:0 0 6px 0; color:#38bdf8; font-size:14px;">✈️ Telegram Bot Setup (Free Phone Push Alerts & 2-Way Assistant)</h4>
                    <p style="margin:0 0 8px 0; color:var(--text-muted); font-size:11px;">Create a bot with @BotFather and get your chat ID from @userinfobot</p>
                    <label style="font-size:12px; color:var(--text-muted); display:block; margin-bottom:4px;">Telegram Bot Token:</label>
                    <input type="text" id="tg-token-input" class="input-box" placeholder="e.g. 123456789:ABCdefGhIJKlmNoPQRstuVWXyz" style="margin-bottom:8px;">
                    <label style="font-size:12px; color:var(--text-muted); display:block; margin-bottom:4px;">Telegram Chat ID:</label>
                    <input type="text" id="tg-chat-input" class="input-box" placeholder="e.g. 987654321">
                </div>

                <div style="background:#090d16; padding:12px; border-radius:8px; border:1px solid var(--border);">
                    <h4 style="margin:0 0 6px 0; color:#10b981; font-size:14px;">📬 1-Click Direct Cold Email Dispatcher (Gmail SMTP)</h4>
                    <p style="margin:0 0 8px 0; color:var(--text-muted); font-size:11px;">Send cold emails with your tailored PDF resume attached in 1 click!</p>
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-bottom:8px;">
                        <div>
                            <label style="font-size:12px; color:var(--text-muted); display:block; margin-bottom:4px;">Sender Email (Gmail):</label>
                            <input type="email" id="smtp-user-input" class="input-box" placeholder="youremail@gmail.com" style="margin:0;">
                        </div>
                        <div>
                            <label style="font-size:12px; color:var(--text-muted); display:block; margin-bottom:4px;">Google App Password (16-char):</label>
                            <input type="password" id="smtp-pass-input" class="input-box" placeholder="xxxx xxxx xxxx xxxx" style="margin:0;" title="Get this at https://myaccount.google.com/apppasswords">
                        </div>
                    </div>
                    <label style="font-size:12px; color:var(--text-muted); display:block; margin-bottom:4px;">Sender Full Name:</label>
                    <input type="text" id="smtp-name-input" class="input-box" placeholder="Sasi Kumar Reddy Chintala">
                </div>

                <div style="background:#090d16; padding:12px; border-radius:8px; border:1px solid var(--border);">
                    <h4 style="margin:0 0 6px 0; color:#f59e0b; font-size:14px;">📊 Google Sheets & Notion Live Tracker Sync</h4>
                    <p style="margin:0 0 8px 0; color:var(--text-muted); font-size:11px;">Automatically syncs evaluated, qualified, and submitted jobs in real time.</p>
                    <label style="font-size:12px; color:var(--text-muted); display:block; margin-bottom:4px;">Google Sheets Webhook URL (Google Apps Script):</label>
                    <input type="text" id="sheets-webhook-input" class="input-box" placeholder="https://script.google.com/macros/s/.../exec" style="margin-bottom:8px;">
                    
                    <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
                        <div>
                            <label style="font-size:12px; color:var(--text-muted); display:block; margin-bottom:4px;">Notion API Key:</label>
                            <input type="password" id="notion-key-input" class="input-box" placeholder="secret_..." style="margin:0;">
                        </div>
                        <div>
                            <label style="font-size:12px; color:var(--text-muted); display:block; margin-bottom:4px;">Notion Database ID:</label>
                            <input type="text" id="notion-db-input" class="input-box" placeholder="e.g. 1a2b3c4d..." style="margin:0;">
                        </div>
                    </div>
                </div>

                <div style="background:#090d16; padding:12px; border-radius:8px; border:1px solid var(--border);">
                    <h4 style="margin:0 0 6px 0; color:#818cf8; font-size:14px;">🎮 Discord Channel Webhook</h4>
                    <p style="margin:0 0 8px 0; color:var(--text-muted); font-size:11px;">Server Settings &gt; Integrations &gt; Webhooks &gt; New Webhook</p>
                    <label style="font-size:12px; color:var(--text-muted); display:block; margin-bottom:4px;">Discord Webhook URL:</label>
                    <input type="text" id="dc-webhook-input" class="input-box" placeholder="https://discord.com/api/webhooks/...">
                </div>

                <div style="display:flex; justify-content:space-between; gap:10px; margin-top:8px;">
                    <button class="btn btn-outline" style="font-size:12px;" onclick="sendTestAlert()">🧪 Send Test Alert</button>
                    <button class="btn btn-green" style="font-size:12px;" onclick="saveNotificationSettings()">💾 Save Credentials</button>
                </div>
            </div>
        </div>
    </div>

    <!-- 7-Day Follow-Up Modal -->
    <div id="followup-modal" class="modal-overlay">
        <div class="modal-content" style="max-width: 800px;">
            <div class="modal-header">
                <div>
                    <h3 style="margin:0; font-size:18px; color:var(--text-main);">⏰ 7-Day Recruiter Follow-Up Reminders</h3>
                    <p style="margin:4px 0 0 0; font-size:12px; color:var(--text-muted);">
                        40% of interview callbacks happen after sending a polite follow-up 5–7 days after applying.
                    </p>
                </div>
                <button class="btn btn-outline" style="padding:4px 10px;" onclick="closeFollowupModal()">✕</button>
            </div>
            <div id="followup-list-container" style="display:flex; flex-direction:column; gap:12px; max-height:65vh; overflow-y:auto; padding-right:4px;">
                <p style="color:var(--text-muted); font-size:13px; text-align:center;">Loading pending follow-ups...</p>
            </div>
        </div>
    </div>

    <!-- Toast -->
    <div id="copy-toast" class="toast">✅ Copied to clipboard!</div>

    <div class="header">
        <div>
            <h1>Personal AI Job Application Agent</h1>
            <p id="candidate-info" style="margin: 4px 0 0 0; color: var(--text-muted); font-size: 14px;">Candidate: Loading profile...</p>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <input type="file" id="resume-file-input" accept=".pdf,.docx" style="display: none;" onchange="handleResumeUpload(this.files[0])">
            <button class="btn btn-outline" onclick="document.getElementById('resume-file-input').click()">📄 Upload Resume</button>
            <button class="btn btn-outline" onclick="openFollowupModal()">⏰ Follow-Ups <span id="followup-count-badge" class="badge" style="background:#f59e0b; color:#000; margin-left:4px; display:none;">0</span></button>
            <button class="btn btn-outline" onclick="syncTrackerNow()">📊 Sync Tracker</button>
            <button class="btn btn-outline" onclick="openNotifModal()">⚙️ Settings</button>
            <button class="btn btn-outline" onclick="clearData()">🧹 Clear Data</button>
            <button class="btn btn-green" onclick="runFullPipeline()">🚀 Auto-Apply to All Qualified</button>
        </div>
    </div>

    <div class="card" style="background: linear-gradient(135deg, rgba(30,41,59,0.7) 0%, rgba(15,23,42,0.85) 100%); border-left: 4px solid var(--warning);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
                <h3 style="margin: 0; font-size: 15px; color: var(--warning); display: flex; align-items: center; gap: 6px;">
                    ⏰ Morning Auto-Pilot (Hands-Free Discovery)
                </h3>
                <p id="scheduler-status-text" style="margin: 4px 0 0 0; color: var(--text-muted); font-size: 12px;">
                    Runs daily autonomous search, 100-point JD scoring, and tailored PDF resume generation while you sleep.
                </p>
            </div>
            <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                <label style="font-size: 12px; color: var(--text-muted);">Daily Run Time:</label>
                <input type="time" id="schedule-time-input" value="08:00" class="input-box" style="margin: 0; padding: 5px 8px; font-size: 12px; max-width: 100px;" onchange="updateScheduleTime()">
                <button id="btn-toggle-scheduler" class="btn btn-outline" style="font-size: 12px; padding: 6px 14px;" onclick="toggleScheduler()">▶ Enable Auto-Pilot</button>
                <button class="btn btn-outline" style="font-size: 12px; padding: 6px 12px;" onclick="triggerScheduledRunNow()">⚡ Run Now</button>
            </div>
        </div>
        <div id="scheduler-next-run" style="margin-top: 8px; font-size: 11px; color: #38bdf8;">Status: Inactive</div>
    </div>

    <div class="card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
            <h2 style="font-size: 15px; margin: 0; color: var(--accent);">⚡ 1-Click Search & Score (Cutshort, Instahyre, Wellfound, Turing, Hirist, Hirect, Internshala, RemoteOK, Naukri, LinkedIn)</h2>
        </div>
        
        <!-- Categorized Role Chips -->
        <div style="margin-top:10px; display:flex; flex-direction:column; gap:8px;">
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                <span style="font-size:11px; color:#38bdf8; font-weight:700; text-transform:uppercase; min-width:85px;">🎯 Experience:</span>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#38bdf8; color:#7dd3fc; background:rgba(56,189,248,0.1);" onclick="setExpPreset('1-2 years')">🎯 1-2 Years Experience</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#34d399; color:#6ee7b7; background:rgba(52,211,153,0.1);" onclick="setExpPreset('Fresher 0-1 year')">🌱 Fresher / 0-1 Year</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#818cf8; color:#a5b4fc; background:rgba(129,140,248,0.1);" onclick="setExpPreset('Junior 0-2 years')">🚀 Junior / 0-2 Years</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#f472b6; color:#fbcfe8;" onclick="setSearchPreset('Junior AI Engineer 0-2 years')">🤖 Jr AI Engineer (0-2 Yrs)</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#fbbf24; color:#fde68a;" onclick="setSearchPreset('Junior Python Developer 1-2 years')">🐍 Jr Python (1-2 Yrs)</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#2dd4bf; color:#99f6e4;" onclick="setSearchPreset('Junior Data Analyst 0-2 years')">📊 Jr Data Analyst (0-2 Yrs)</button>
            </div>
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                <span style="font-size:11px; color:#818cf8; font-weight:700; text-transform:uppercase; min-width:85px;">🤖 AI & Data:</span>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#818cf8; color:#a5b4fc;" onclick="setSearchPreset('AI Engineer 0-2 years')">🤖 AI Engineer</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#f472b6; color:#fbcfe8;" onclick="setSearchPreset('Generative AI Python 1-2 years')">⚡ GenAI & LLM Dev</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#38bdf8; color:#7dd3fc;" onclick="setSearchPreset('Machine Learning Engineer 0-2 years')">🧠 ML Engineer</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#34d399; color:#6ee7b7;" onclick="setSearchPreset('Data Analyst 0-2 years')">📊 Data Analyst</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#c084fc; color:#e9d5ff;" onclick="setSearchPreset('AI Agent Developer LangChain 1-2 years')">🤖 AI Agent Dev</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#fb923c; color:#fed7aa;" onclick="setSearchPreset('Prompt Engineer RAG 0-2 years')">🔮 Prompt / RAG</button>
            </div>
            <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                <span style="font-size:11px; color:#34d399; font-weight:700; text-transform:uppercase; min-width:85px;">💻 Software & Jr:</span>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#34d399; color:#a7f3d0;" onclick="setSearchPreset('Associate Software Developer 0-2 years')">🚀 Associate SWE</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#fbbf24; color:#fde68a;" onclick="setSearchPreset('Junior Python Developer 0-2 years')">🐍 Jr Python Dev</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#60a5fa; color:#bfdbfe;" onclick="setSearchPreset('Backend Developer FastAPI 1-2 years')">💼 Backend Developer</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#a855f7; color:#ddd6fe;" onclick="setSearchPreset('Junior Data Engineer 0-2 years')">🛠️ Jr Data Engineer</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#2dd4bf; color:#99f6e4;" onclick="setSearchPreset('Full Stack Python Developer 0-2 years')">🌐 Full Stack Python</button>
                <button class="btn btn-outline" style="font-size:11px; padding:3px 9px; border-color:#94a3b8; color:#cbd5e1;" onclick="setSearchPreset('Software Engineer Fresher 0-2 years')">🎯 Fresher / Entry Level</button>
            </div>
        </div>

        <div class="search-bar" style="margin-top:12px;">
            <select id="search-query" class="input-box" style="flex: 2; min-width: 240px; cursor: pointer;">
                <optgroup label="🔥 Most Popular / Candidate Target Roles">
                    <option value="Junior Python Developer 0-2 years" selected>🐍 Junior Python Developer (0-2 Yrs)</option>
                    <option value="Junior AI Engineer 0-2 years">🤖 Junior AI Engineer (0-2 Yrs)</option>
                    <option value="Generative AI Python 1-2 years">⚡ GenAI &amp; LLM Developer (1-2 Yrs)</option>
                    <option value="Associate Software Developer 0-2 years">🚀 Associate Software Engineer (0-2 Yrs)</option>
                    <option value="Junior Data Analyst 0-2 years">📊 Junior Data Analyst (0-2 Yrs)</option>
                    <option value="Junior Data Engineer 0-2 years">🛠️ Junior Data Engineer (0-2 Yrs)</option>
                </optgroup>
                <optgroup label="🤖 AI, GenAI &amp; Machine Learning">
                    <option value="AI Engineer 0-2 years">🤖 AI Engineer (0-2 Yrs)</option>
                    <option value="AI Agent Developer LangChain 1-2 years">🧠 AI Agent Developer / LangChain (1-2 Yrs)</option>
                    <option value="Prompt Engineer RAG 0-2 years">🔮 Prompt Engineer &amp; RAG (0-2 Yrs)</option>
                    <option value="Machine Learning Engineer 0-2 years">🧠 Machine Learning Engineer (0-2 Yrs)</option>
                    <option value="NLP Engineer Python 0-2 years">💬 NLP / LLM Engineer (0-2 Yrs)</option>
                    <option value="Computer Vision Engineer Python 0-2 years">👁️ Computer Vision Engineer (0-2 Yrs)</option>
                    <option value="Deep Learning Engineer 0-2 years">🔬 Deep Learning Engineer (0-2 Yrs)</option>
                </optgroup>
                <optgroup label="💻 Software &amp; Backend Engineering">
                    <option value="Python Developer 1-2 years">🐍 Python Developer (1-2 Yrs)</option>
                    <option value="Backend Developer FastAPI 1-2 years">💼 Backend Developer (FastAPI / Django) (1-2 Yrs)</option>
                    <option value="Full Stack Python Developer 0-2 years">🌐 Full Stack Python Developer (0-2 Yrs)</option>
                    <option value="Software Development Engineer SDE 1">💻 SDE-1 / Software Developer 1 (0-2 Yrs)</option>
                    <option value="API Microservices Engineer Python 0-2 years">⚙️ API / Microservices Engineer (0-2 Yrs)</option>
                    <option value="Java Developer 0-2 years">☕ Java Developer (0-2 Yrs)</option>
                    <option value="Node.js Backend Developer 0-2 years">🟢 Node.js / TypeScript Developer (0-2 Yrs)</option>
                    <option value="React Frontend Developer 0-2 years">⚛️ React / Frontend Developer (0-2 Yrs)</option>
                </optgroup>
                <optgroup label="📊 Data, Analytics &amp; BI">
                    <option value="Data Analyst 0-2 years">📊 Data Analyst (SQL / Python / PowerBI) (0-2 Yrs)</option>
                    <option value="Data Scientist 0-2 years">📈 Data Scientist (0-2 Yrs)</option>
                    <option value="Data Engineer 0-2 years">🛠️ Data Engineer (ETL / Pipelines) (0-2 Yrs)</option>
                    <option value="Business Intelligence Analyst 0-2 years">📋 BI / Business Analyst (0-2 Yrs)</option>
                </optgroup>
                <optgroup label="🌱 Fresher, Intern &amp; Entry Level">
                    <option value="Software Engineer Fresher 0-1 year">🌱 Software Engineer Fresher (0-1 Yr)</option>
                    <option value="Python Developer Fresher 0-1 year">🐍 Python Developer Fresher (0-1 Yr)</option>
                    <option value="Graduate Engineer Trainee 0-1 year">🎓 Graduate Engineer Trainee (GET) (0-1 Yr)</option>
                    <option value="AI / ML Intern Fresher">💡 AI / ML Intern (Fresher)</option>
                    <option value="Software Development Intern">💻 Software Development Intern</option>
                </optgroup>
                <optgroup label="☁️ Cloud, DevOps, QA &amp; Cyber">
                    <option value="Cloud Engineer AWS Azure 0-2 years">☁️ Cloud Engineer (AWS / Azure) (0-2 Yrs)</option>
                    <option value="DevOps Engineer 0-2 years">♾️ DevOps / CI-CD Engineer (0-2 Yrs)</option>
                    <option value="QA Automation Engineer Python 0-2 years">🧪 QA Automation Engineer (Python / Selenium) (0-2 Yrs)</option>
                    <option value="Cybersecurity Analyst 0-2 years">🛡️ Cybersecurity Analyst (0-2 Yrs)</option>
                </optgroup>
            </select>

            <select id="search-location" class="input-box" style="flex: 1.5; min-width: 190px; cursor: pointer;">
                <optgroup label="🇮🇳 Top India Tech Cities">
                    <option value="Bengaluru" selected>📍 Bengaluru / Bangalore</option>
                    <option value="Hyderabad">📍 Hyderabad</option>
                    <option value="Pune">📍 Pune</option>
                    <option value="Delhi NCR (Gurgaon / Noida)">📍 Delhi NCR (Gurgaon / Noida / Delhi)</option>
                    <option value="Mumbai">📍 Mumbai / Navi Mumbai</option>
                    <option value="Chennai">📍 Chennai</option>
                    <option value="Kolkata">📍 Kolkata</option>
                    <option value="Ahmedabad">📍 Ahmedabad / Gandhinagar</option>
                    <option value="Kochi / Trivandrum">📍 Kochi / Trivandrum (Kerala)</option>
                    <option value="Chandigarh / Mohali">📍 Chandigarh / Mohali</option>
                    <option value="Coimbatore">📍 Coimbatore</option>
                    <option value="Jaipur">📍 Jaipur</option>
                    <option value="India">🇮🇳 Pan India / Any Location (India)</option>
                </optgroup>
                <optgroup label="🌐 Remote &amp; Global">
                    <option value="Remote">🏠 Remote (India / Work From Home)</option>
                    <option value="Worldwide Remote">🌍 Worldwide Remote / Global</option>
                    <option value="United States Remote">🇺🇸 United States (Remote / US Timezone)</option>
                    <option value="Europe Remote">🇪🇺 UK &amp; Europe (Remote)</option>
                    <option value="All">🌐 Any Location / Worldwide</option>
                </optgroup>
            </select>

            <select id="search-exp" class="input-box" style="max-width: 170px; cursor: pointer;">
                <option value="0-2 years" selected>🎯 0–2 Years / Fresher</option>
                <option value="1-2 years">🎯 1–2 Years Exp</option>
                <option value="Fresher 0-1 year">🌱 Fresher (0–1 Yr)</option>
                <option value="all">Any Experience</option>
            </select>
            <select id="search-time" class="input-box" style="max-width: 150px; cursor: pointer;">
                <option value="24h">Past 24 Hours</option>
                <option value="3d" selected>Past 3 Days</option>
                <option value="7d">Past 7 Days</option>
            </select>
            <button class="btn" id="btn-search-score" onclick="searchAndScore()">⚡ Search 0-2 Yrs Jobs</button>
        </div>
        <p id="search-status" style="font-size: 13px; color: var(--accent); margin: 10px 0 0 0; font-weight: 500;"></p>
    </div>

    <!-- Live Activity Terminal -->
    <div>
        <div class="log-panel-header">
            <span style="font-size: 13px; color: var(--text-muted); font-weight: 600;">📡 Live Agent Activity</span>
            <div style="display:flex;gap:10px;align-items:center;">
                <span id="log-status-dot" class="log-dot idle"></span>
                <span id="log-status-text" style="font-size: 12px; color: var(--text-muted);">Idle</span>
                <button onclick="document.getElementById('log-panel').innerHTML=''; " style="background:transparent;border:1px solid #1e293b;color:var(--text-muted);padding:3px 10px;border-radius:4px;cursor:pointer;font-size:12px;">Clear</button>
            </div>
        </div>
        <div id="log-panel" class="log-panel">
            <div class="log-line" style="color:#4b6075;">Waiting for agent activity...</div>
        </div>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">Total Discovered</div>
            <div class="stat-val" id="stat-total">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Qualified (Fit Score &ge; 70)</div>
            <div class="stat-val" id="stat-qualified" style="color: var(--accent);">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Tailored Resumes Ready</div>
            <div class="stat-val" id="stat-resumes" style="color: var(--warning);">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Ready / Submitted</div>
            <div class="stat-val" id="stat-submitted" style="color: var(--success);">0</div>
        </div>
    </div>
            <h2 style="font-size: 18px; margin: 0;">Discovered Openings & Match Evaluations</h2>
            <label style="font-size: 13px; color: var(--text-muted); cursor: pointer;">
                <input type="checkbox" id="filter-matched-only" onchange="loadData()"> Show Only Qualified Jobs (&ge; 70 Score)
            </label>
        </div>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Source</th>
                    <th>Company</th>
                    <th>Job Title</th>
                    <th>Match Score</th>
                    <th>Fit Decision</th>
                    <th>Status</th>
                    <th>Applied Resume</th>
                    <th>Outreach Note</th>
                    <th>Job URL</th>
                </tr>
            </thead>
            <tbody id="app-rows">
                <tr><td colspan="10" style="text-align: center; color: var(--text-muted);">Loading applications...</td></tr>
            </tbody>
        </table>
    </div>

    <script>
        let currentOutreachData = null;
        let currentJobId = null;

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
                } else {
                    document.getElementById('text-li').innerText = "Failed to load outreach template.";
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

                    prepFormatted += `⭐ STAR-METHOD TALKING POINTS (PROVEN EXPERIENCE)\n` +
                                     `==============================================================\n\n`;
                    prepJson.star_stories.forEach((s, idx) => {
                        prepFormatted += `Story ${idx+1}: ${s.title}\n` +
                                         `• Situation: ${s.situation}\n` +
                                         `• Task: ${s.task}\n` +
                                         `• Action: ${s.action}\n` +
                                         `• Result: ${s.result}\n\n`;
                    });

                    prepFormatted += `💡 SMART QUESTIONS TO ASK THE INTERVIEWER\n` +
                                     `==============================================================\n`;
                    prepJson.questions_to_ask.forEach(q => {
                        prepFormatted += `${q}\n`;
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
                alert("Please enter the recipient's email address (e.g. careers@company.com or hiring.manager@company.com).");
                return;
            }

            statusDiv.style.display = 'block';
            statusDiv.style.background = 'rgba(56,189,248,0.15)';
            statusDiv.style.color = '#38bdf8';
            statusDiv.style.border = '1px solid rgba(56,189,248,0.3)';
            statusDiv.innerHTML = "⏳ Connecting to SMTP server & dispatching email with tailored PDF resume attached...";

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
                    statusDiv.style.border = '1px solid rgba(16,185,129,0.4)';
                    statusDiv.innerHTML = `✅ <strong>Success!</strong> ${data.message}`;
                    showToast("Cold email dispatched with tailored PDF resume!");
                    await loadData();
                } else {
                    statusDiv.style.background = 'rgba(239,68,68,0.18)';
                    statusDiv.style.color = '#f87171';
                    statusDiv.style.border = '1px solid rgba(239,68,68,0.4)';
                    statusDiv.innerHTML = `❌ <strong>Failed:</strong> ${data.error || 'Check SMTP credentials in Alerts Setup'}`;
                }
            } catch(e) {
                statusDiv.style.background = 'rgba(239,68,68,0.18)';
                statusDiv.style.color = '#f87171';
                statusDiv.innerHTML = `❌ Error: ${e}`;
            }
        }

        function copyEmailBodyFromTextarea() {
            const bodyText = document.getElementById('text-email-body').value;
            navigator.clipboard.writeText(bodyText);
            showToast("Copied email body to clipboard!");
        }

        function closeOutreachModal() {
            document.getElementById('outreach-modal').classList.remove('open');
        }

        function switchOutreachTab(tab) {
            document.getElementById('tab-li').classList.remove('active');
            document.getElementById('tab-email').classList.remove('active');
            document.getElementById('tab-inmail').classList.remove('active');
            document.getElementById('tab-cl').classList.remove('active');
            document.getElementById('tab-prep').classList.remove('active');

            document.getElementById('view-li').style.display = 'none';
            document.getElementById('view-email').style.display = 'none';
            document.getElementById('view-inmail').style.display = 'none';
            document.getElementById('view-cl').style.display = 'none';
            document.getElementById('view-prep').style.display = 'none';

            if (tab === 'li') {
                document.getElementById('tab-li').classList.add('active');
                document.getElementById('view-li').style.display = 'block';
            } else if (tab === 'email') {
                document.getElementById('tab-email').classList.add('active');
                document.getElementById('view-email').style.display = 'block';
            } else if (tab === 'inmail') {
                document.getElementById('tab-inmail').classList.add('active');
                document.getElementById('view-inmail').style.display = 'block';
            } else if (tab === 'cl') {
                document.getElementById('tab-cl').classList.add('active');
                document.getElementById('view-cl').style.display = 'block';
            } else if (tab === 'prep') {
                document.getElementById('tab-prep').classList.add('active');
                document.getElementById('view-prep').style.display = 'block';
            }
        }

        function showToast(msg = "Copied to clipboard!") {
            const toast = document.getElementById('copy-toast');
            toast.innerText = `✅ ${msg}`;
            toast.style.display = 'block';
            setTimeout(() => { toast.style.display = 'none'; }, 2500);
        }

        function copyModalText(elementId) {
            const text = document.getElementById(elementId).innerText;
            navigator.clipboard.writeText(text);
            showToast("Copied message to clipboard!");
        }

        function copyInputVal(elementId) {
            const text = document.getElementById(elementId).value;
            navigator.clipboard.writeText(text);
            showToast("Copied subject to clipboard!");
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
                let apps = await res.json();
                
                document.getElementById('stat-total').innerText = apps.length;
                document.getElementById('stat-qualified').innerText = apps.filter(a => a.decision === 'HIGH' || a.decision === 'VERY_HIGH' || (a.match_score && a.match_score >= 70)).length;
                document.getElementById('stat-resumes').innerText = apps.filter(a => a.tailored_resume_path).length;
                document.getElementById('stat-submitted').innerText = apps.filter(a => a.status === 'READY_TO_SUBMIT' || a.status === 'SUBMITTED').length;

                const matchedOnly = document.getElementById('filter-matched-only') && document.getElementById('filter-matched-only').checked;
                if (matchedOnly) {
                    apps = apps.filter(a => a.decision === 'HIGH' || a.decision === 'VERY_HIGH' || (a.match_score && a.match_score >= 70));
                }

                const tbody = document.getElementById('app-rows');
                if (apps.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: var(--text-muted);">No matching jobs found. Click \"⚡ Search & Score Match\" above.</td></tr>';
                    return;
                }

                tbody.innerHTML = apps.map(a => {
                    let scoreHtml = '-';
                    if (a.match_score !== null && a.match_score !== undefined) {
                        const sClass = a.match_score >= 80 ? 'score-high' : a.match_score >= 65 ? 'score-med' : 'score-low';
                        scoreHtml = `<span class="${sClass}">${a.match_score}/100</span>`;
                    }
                    let resumeHtml = '<span style="color:var(--text-muted);">-</span>';
                    if (a.tailored_resume_path) {
                        const filename = a.tailored_resume_path.split(/[\\\\/]/).pop();
                        resumeHtml = `<a href="/api/view-resume?file=${encodeURIComponent(a.tailored_resume_path)}" target="_blank" class="link" style="color:var(--warning);font-size:12px;font-weight:600;" title="${filename}">📄 Tailored PDF ↗</a>`;
                    }
                    let srcBadge = `<span style="font-size: 10px; text-transform: uppercase; color: var(--accent);">${a.source || 'Live'}</span>`;
                    const srcLow = (a.source || '').toLowerCase();
                    if (srcLow.includes('python_org')) {
                        srcBadge = `<span style="background:rgba(16,185,129,0.18);color:#34d399;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(16,185,129,0.3);" title="Low Competition & High Shortlisting Chance">★ Python.org (High Chance)</span>`;
                    } else if (srcLow.includes('ashby')) {
                        srcBadge = `<span style="background:rgba(16,185,129,0.22);color:#10b981;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(16,185,129,0.4);" title="Ashby Direct Modern Scaleup ATS">⭐ Ashby Direct (Top Scaleup)</span>`;
                    } else if (srcLow.includes('hacker_news')) {
                        srcBadge = `<span style="background:rgba(249,115,22,0.2);color:#fb923c;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(249,115,22,0.4);" title="Hacker News Who is Hiring (Direct Founder)">🔥 HN / YC (Direct Founder)</span>`;
                    } else if (srcLow.includes('wellfound')) {
                        srcBadge = `<span style="background:rgba(239,68,68,0.18);color:#f87171;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(239,68,68,0.3);" title="Wellfound #1 AI & Startup Platform">🦄 Wellfound (AngelList)</span>`;
                    } else if (srcLow.includes('turing')) {
                        srcBadge = `<span style="background:rgba(16,185,129,0.2);color:#34d399;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(16,185,129,0.4);" title="Turing Remote AI/ML Platform">🌍 Turing (Remote AI)</span>`;
                    } else if (srcLow.includes('cutshort')) {
                        srcBadge = `<span style="background:rgba(236,72,153,0.18);color:#f472b6;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(236,72,153,0.3);" title="Cutshort Fast Startup Shortlisting">🚀 Cutshort</span>`;
                    } else if (srcLow.includes('instahyre')) {
                        srcBadge = `<span style="background:rgba(168,85,247,0.18);color:#c084fc;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(168,85,247,0.3);" title="Instahyre Premium Tech Roles">⚡ Instahyre</span>`;
                    } else if (srcLow.includes('hirist')) {
                        srcBadge = `<span style="background:rgba(14,165,233,0.18);color:#38bdf8;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(14,165,233,0.3);" title="Hirist Curated Tech Portal">💎 Hirist.tech</span>`;
                    } else if (srcLow.includes('hirect')) {
                        srcBadge = `<span style="background:rgba(245,158,11,0.2);color:#fbbf24;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(245,158,11,0.4);" title="Hirect Direct Founder Chat Hiring">💬 Hirect</span>`;
                    } else if (srcLow.includes('internshala')) {
                        srcBadge = `<span style="background:rgba(59,130,246,0.18);color:#60a5fa;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(59,130,246,0.3);" title="Internshala AI/ML Roles">🎓 Internshala</span>`;
                    } else if (srcLow.includes('remoteok')) {
                        srcBadge = `<span style="background:rgba(234,88,12,0.18);color:#fb923c;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(234,88,12,0.3);" title="RemoteOK AI/Tech Portal">🌐 RemoteOK</span>`;
                    } else if (srcLow.includes('naukri')) {
                        srcBadge = `<span style="background:rgba(99,102,241,0.18);color:#a5b4fc;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(99,102,241,0.3);" title="Naukri AI/ML Portal">💼 Naukri (AI/ML)</span>`;
                    } else if (srcLow.includes('indeed')) {
                        srcBadge = `<span style="background:rgba(59,130,246,0.18);color:#60a5fa;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(59,130,246,0.3);">Indeed</span>`;
                    } else if (srcLow.includes('greenhouse') || srcLow.includes('lever')) {
                        srcBadge = `<span style="background:rgba(99,102,241,0.18);color:#a5b4fc;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(99,102,241,0.3);" title="Direct Company ATS Portal">⚡ Direct ATS</span>`;
                    } else if (srcLow.includes('remotive') || srcLow.includes('arbeitnow') || srcLow.includes('jobicy') || srcLow.includes('weworkremotely') || srcLow.includes('himalayas')) {
                        srcBadge = `<span style="background:rgba(56,189,248,0.18);color:#38bdf8;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;border:1px solid rgba(56,189,248,0.3);">${a.source}</span>`;
                    } else if (srcLow.includes('linkedin')) {
                        srcBadge = `<span style="background:rgba(148,163,184,0.15);color:#cbd5e1;padding:3px 7px;border-radius:4px;font-size:10px;font-weight:700;">🔗 LinkedIn</span>`;
                    }

                    const outreachBtn = `<button onclick="openOutreachModal(${a.job_id})" style="background:rgba(99,102,241,0.18);border:1px solid rgba(99,102,241,0.4);color:#c7d2fe;padding:4px 8px;border-radius:6px;font-size:11px;font-weight:600;cursor:pointer;display:inline-flex;align-items:center;gap:4px;">✉️ Note</button>`;

                    return `
                    <tr>
                        <td>${a.job_id}</td>
                        <td>${srcBadge}</td>
                        <td><strong>${a.company}</strong></td>
                        <td>${a.title}</td>
                        <td>${scoreHtml}</td>
                        <td><strong>${a.decision || '-'}</strong></td>
                        <td><span class="badge badge-${a.status}">${a.status}</span></td>
                        <td>${resumeHtml}</td>
                        <td>${outreachBtn}</td>
                        <td><a href="${a.url || '#'}" target="_blank" class="link">View Job ↗</a></td>
                    </tr>
                    `;
                }).join('');
                await loadFollowups();
            } catch (e) {
                console.error(e);
            }
        }

        let pollInterval = null;

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
                    if (querySelect.options[i].value === role || querySelect.options[i].value.toLowerCase().includes(role.toLowerCase()) || role.toLowerCase().includes(querySelect.options[i].value.toLowerCase())) {
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

        async function searchAndScore() {
            let query = document.getElementById('search-query').value;
            const location = document.getElementById('search-location').value;
            const time_range = document.getElementById('search-time').value;
            const exp = document.getElementById('search-exp') ? document.getElementById('search-exp').value : '';
            const status = document.getElementById('search-status');
            const btn = document.getElementById('btn-search-score');

            if (exp && exp !== 'all' && !query.toLowerCase().includes('year') && !query.toLowerCase().includes('fresher')) {
                query = `${query} ${exp}`;
            }

            status.innerText = `⏳ Running 0-2 Yrs Targeted Search for '${query}' in '${location}' (${time_range}). Watch live logs below...`;
            btn.disabled = true;

            try {
                await fetch('/api/search-and-match', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query, location, time_range})
                });

                if (pollInterval) clearInterval(pollInterval);
                let checkCount = 0;
                pollInterval = setInterval(async () => {
                    await loadData();
                    checkCount++;
                    // After 60 checks (3 minutes) or when idle, keep updating
                    if (checkCount > 90) {
                        clearInterval(pollInterval);
                        btn.disabled = false;
                        status.innerText = "✅ Search & Matching finished! Review your scores below.";
                    }
                }, 3000);
            } catch (e) {
                status.innerText = `❌ Error: ${e}`;
                btn.disabled = false;
            }
        }

        async function runFullPipeline() {
            const status = document.getElementById('search-status');
            status.innerText = "⏳ Running automated applications in browser. Watch live terminal below...";
            try {
                await fetch('/api/run-agent', {method: 'POST'});
                if (pollInterval) clearInterval(pollInterval);
                pollInterval = setInterval(async () => {
                    await loadData();
                }, 4000);
            } catch (e) {
                status.innerText = `❌ Pipeline error: ${e}`;
            }
        }

        function handleResumeUpload(file) {
            if (!file) return;
            const reader = new FileReader();
            const status = document.getElementById('search-status');
            status.innerText = `⏳ Uploading and parsing ${file.name} with AI...`;
            
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
                        status.innerText = `✅ Resume imported successfully for ${data.profile.contact_info.full_name}!`;
                        await loadProfile();
                    } else {
                        status.innerText = `❌ Upload failed: ${data.error || 'Unknown error'}`;
                    }
                } catch (e) {
                    status.innerText = `❌ Error uploading resume: ${e}`;
                }
            };
            reader.readAsDataURL(file);
        }

        async function clearData() {
            if (confirm("Clear all application history from the database?")) {
                await fetch('/api/clear', {method: 'POST'});
                await loadData();
            }
        }

        async function loadSchedulerStatus() {
            try {
                const res = await fetch('/api/scheduler');
                const s = await res.json();
                const btn = document.getElementById('btn-toggle-scheduler');
                const info = document.getElementById('scheduler-next-run');
                const timeInput = document.getElementById('schedule-time-input');

                if (s.schedule_time) timeInput.value = s.schedule_time;

                if (s.enabled) {
                    btn.innerText = '⏸ Pause Auto-Pilot';
                    btn.classList.add('btn-green');
                    btn.classList.remove('btn-outline');
                    info.innerHTML = `🟢 <strong>Active</strong> &bull; Next run scheduled for: <strong>${s.next_run}</strong> (Last run: ${s.last_run || 'None yet'})`;
                } else {
                    btn.innerText = '▶ Enable Auto-Pilot';
                    btn.classList.remove('btn-green');
                    btn.classList.add('btn-outline');
                    info.innerHTML = `⚪ <strong>Inactive</strong> &bull; Set daily run time and click Enable (Last run: ${s.last_run || 'None yet'})`;
                }
            } catch(e) {
                console.error(e);
            }
        }

        async function toggleScheduler() {
            const timeVal = document.getElementById('schedule-time-input').value;
            const res = await fetch('/api/scheduler/toggle', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ schedule_time: timeVal })
            });
            await loadSchedulerStatus();
            showToast("Auto-Pilot settings updated!");
        }

        async function updateScheduleTime() {
            const timeVal = document.getElementById('schedule-time-input').value;
            await fetch('/api/scheduler/update-time', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ schedule_time: timeVal })
            });
            await loadSchedulerStatus();
        }

        async function triggerScheduledRunNow() {
            const status = document.getElementById('search-status');
            status.innerText = "⏳ Running Morning Discovery & Scoring pipeline now. Watch live activity below...";
            showToast("Morning Auto-Pilot triggered!");
            try {
                await fetch('/api/scheduler/run-now', {method: 'POST'});
                if (pollInterval) clearInterval(pollInterval);
                pollInterval = setInterval(async () => {
                    await loadData();
                    await loadSchedulerStatus();
                }, 3000);
            } catch(e) {
                status.innerText = `❌ Error: ${e}`;
            }
        }

        async function openNotifModal() {
            document.getElementById('notif-modal').classList.add('open');
            try {
                const res = await fetch('/api/notifications');
                const d = await res.json();
                if (d.tg_token) document.getElementById('tg-token-input').value = d.tg_token;
                if (d.tg_chat_id) document.getElementById('tg-chat-input').value = d.tg_chat_id;
                if (d.discord_webhook) document.getElementById('dc-webhook-input').value = d.discord_webhook;
                if (d.smtp_user) document.getElementById('smtp-user-input').value = d.smtp_user;
                if (d.smtp_password) document.getElementById('smtp-pass-input').value = d.smtp_password;
                if (d.smtp_from_name) document.getElementById('smtp-name-input').value = d.smtp_from_name;
                if (d.sheets_webhook) document.getElementById('sheets-webhook-input').value = d.sheets_webhook;
                if (d.notion_key) document.getElementById('notion-key-input').value = d.notion_key;
                if (d.notion_db) document.getElementById('notion-db-input').value = d.notion_db;
            } catch(e) {
                console.error(e);
            }
        }

        function closeNotifModal() {
            document.getElementById('notif-modal').classList.remove('open');
        }

        async function saveNotificationSettings() {
            const tgToken = document.getElementById('tg-token-input').value.trim();
            const tgChat = document.getElementById('tg-chat-input').value.trim();
            const dcWebhook = document.getElementById('dc-webhook-input').value.trim();
            const smtpUser = document.getElementById('smtp-user-input').value.trim();
            const smtpPass = document.getElementById('smtp-pass-input').value.trim();
            const smtpName = document.getElementById('smtp-name-input').value.trim();
            const sheetsWebhook = document.getElementById('sheets-webhook-input').value.trim();
            const notionKey = document.getElementById('notion-key-input').value.trim();
            const notionDb = document.getElementById('notion-db-input').value.trim();

            const res = await fetch('/api/notifications', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    tg_token: tgToken,
                    tg_chat_id: tgChat,
                    discord_webhook: dcWebhook,
                    smtp_user: smtpUser,
                    smtp_password: smtpPass,
                    smtp_from_name: smtpName,
                    sheets_webhook: sheetsWebhook,
                    notion_key: notionKey,
                    notion_db: notionDb
                })
            });
            const data = await res.json();
            if (data.status === 'SUCCESS') {
                showToast("Settings & Tracker credentials saved!");
                closeNotifModal();
            } else {
                alert("Failed to save settings: " + (data.error || 'Unknown error'));
            }
        }

        async function syncTrackerNow() {
            showToast("Syncing applications to Google Sheets / Notion...");
            try {
                const res = await fetch('/api/sync/all', {method: 'POST'});
                const data = await res.json();
                if (data.status === 'SUCCESS') {
                    showToast(data.message || "Tracker synced successfully!");
                } else {
                    alert("Tracker sync notice: " + (data.error || 'Configure Google Sheets or Notion in Settings'));
                }
            } catch(e) {
                alert("Sync error: " + e);
            }
        }

        let currentFollowupsList = [];

        function copyFollowupLi(idx) {
            if (currentFollowupsList[idx]) {
                navigator.clipboard.writeText(currentFollowupsList[idx].linkedin_followup);
                showToast('Copied LinkedIn note!');
            }
        }

        function copyFollowupEmail(idx) {
            if (currentFollowupsList[idx]) {
                navigator.clipboard.writeText(currentFollowupsList[idx].email_followup_body);
                showToast('Copied Follow-up Email!');
            }
        }

        async function openFollowupModal() {
            document.getElementById('followup-modal').classList.add('open');
            await loadFollowups();
        }

        function closeFollowupModal() {
            document.getElementById('followup-modal').classList.remove('open');
        }

        async function loadFollowups() {
            const container = document.getElementById('followup-list-container');
            const badge = document.getElementById('followup-count-badge');
            try {
                const res = await fetch('/api/followups');
                const data = await res.json();
                if (data.status === 'SUCCESS') {
                    const list = data.followups || [];
                    currentFollowupsList = list;
                    if (list.length > 0) {
                        badge.innerText = list.length;
                        badge.style.display = 'inline-block';
                    } else {
                        badge.style.display = 'none';
                    }

                    if (list.length === 0) {
                        container.innerHTML = `<div style="text-align:center; padding:30px; color:var(--text-muted);">
                            🎉 <strong>All caught up!</strong><br>No applications currently need a 7-day follow-up.
                        </div>`;
                        return;
                    }

                    let html = '';
                    list.forEach((f, idx) => {
                        html += `
                        <div style="background:#090d16; border:1px solid var(--border); border-radius:8px; padding:12px; display:flex; flex-direction:column; gap:8px;">
                            <div style="display:flex; justify-content:space-between; align-items:center;">
                                <div>
                                    <strong style="color:var(--text-main); font-size:14px;">${f.company}</strong>
                                    <span style="color:var(--text-muted); font-size:13px; margin-left:6px;">— ${f.title}</span>
                                </div>
                                <div style="display:flex; gap:6px; align-items:center;">
                                    <span class="badge" style="background:rgba(245,158,11,0.2); color:#fbbf24; border:1px solid rgba(245,158,11,0.4);">⏰ ~${f.days_ago} days ago</span>
                                    <span class="badge badge-success">${f.score}% Fit</span>
                                </div>
                            </div>
                            <div style="background:#0f172a; padding:10px; border-radius:6px; font-size:12px; color:#cbd5e1; border:1px solid #1e293b; line-height:1.5;">
                                💬 <em>"${f.linkedin_followup}"</em>
                            </div>
                            <div style="display:flex; justify-content:flex-end; gap:8px; flex-wrap:wrap;">
                                <button class="btn btn-outline" style="font-size:11px; padding:4px 10px;" onclick="copyFollowupLi(${idx})">📋 Copy LinkedIn Note</button>
                                <button class="btn btn-outline" style="font-size:11px; padding:4px 10px;" onclick="copyFollowupEmail(${idx})">📧 Copy Email Pitch</button>
                                <button class="btn btn-green" style="font-size:11px; padding:4px 10px;" onclick="closeFollowupModal(); openOutreachModal(${f.job_id});">✉️ Open Outreach & Dispatch</button>
                            </div>
                        </div>`;
                    });
                    container.innerHTML = html;
                }
            } catch(e) {
                container.innerHTML = `<p style="color:#ef4444; font-size:12px;">Error loading follow-ups: ${e}</p>`;
            }
        }

        async function sendTestAlert() {
            showToast("Sending test notifications...");
            const res = await fetch('/api/notifications/test', {method: 'POST'});
            const data = await res.json();
            if (data.status === 'SUCCESS') {
                showToast("Test alert dispatched! Check your Telegram / Discord / Desktop.");
            } else {
                alert("Test failed: " + (data.error || 'Unknown error'));
            }
        }

        // ── Live Activity Log (Server-Sent Events) ──────────────────────────
        function startLogStream() {
            const panel = document.getElementById('log-panel');
            const dot   = document.getElementById('log-status-dot');
            const txt   = document.getElementById('log-status-text');

            const es = new EventSource('/api/logs');
            let idleTimer;

            function setActive() {
                dot.classList.remove('idle');
                txt.innerText = 'Active';
                txt.style.color = 'var(--success)';
                clearTimeout(idleTimer);
                idleTimer = setTimeout(() => {
                    dot.classList.add('idle');
                    txt.innerText = 'Idle';
                    txt.style.color = 'var(--text-muted)';
                }, 4000);
            }

            es.onmessage = function(event) {
                try {
                    const d = JSON.parse(event.data);
                    const line = document.createElement('div');
                    line.className = 'log-line';

                    let prefix = '';
                    if (d.level === 'WARNING') prefix = '⚠️ ';
                    else if (d.level === 'ERROR')   prefix = '❌ ';
                    else if (d.level === 'INFO')    prefix = '   ';

                    line.innerHTML = `<span style="color:${d.color};">${prefix}${d.msg.replace(/</g,'&lt;').replace(/>/g,'&gt;')}</span>`;
                    panel.appendChild(line);
                    // auto-scroll to bottom
                    panel.scrollTop = panel.scrollHeight;
                    // remove very old lines to save memory (keep last 300)
                    while (panel.children.length > 300) panel.removeChild(panel.firstChild);
                    setActive();
                } catch(e) {}
            };

            es.onerror = function() {
                dot.classList.add('idle');
                txt.innerText = 'Reconnecting...';
                txt.style.color = 'var(--warning)';
            };
        }

        loadProfile();
        loadData();
        loadSchedulerStatus();
        startLogStream();
    </script>
</body>
</html>
"""

class AgentDashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/healthz", "/ping", "/api/health"):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(b'{"status":"ok","uptime":"live","service":"sasi_job_application_agent"}')
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
            cursor.execute(
                """
                SELECT j.id, j.company, j.title, j.source, j.url, a.status, jm.overall_score, jm.decision, rv.file_path
                FROM jobs j
                JOIN applications a ON j.id = a.job_id
                LEFT JOIN job_matches jm ON j.id = jm.job_id
                LEFT JOIN resume_versions rv ON a.resume_version_id = rv.id
                ORDER BY j.id DESC
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
                    "tailored_resume_path": r[8]
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
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            # Create a per-client queue and register it
            client_q: queue.Queue = queue.Queue(maxsize=200)
            with _sse_lock:
                _sse_clients.append(client_q)
            try:
                # Send a heartbeat comment every 20s to keep the connection alive
                while True:
                    try:
                        data = client_q.get(timeout=20)
                        self.wfile.write(data.encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # Send SSE keep-alive comment
                        self.wfile.write(b": heartbeat\n\n")
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
                    analyzed = jd_agent.analyze_all_pending_jobs(limit=150)
                    logger.info(f" Analyzed {len(analyzed)} pending JDs.")

                    match_agent = MatchAgent()
                    evals = match_agent.evaluate_all_pending_jobs()
                    logger.info(f" Match evaluation complete: {len(evals)} jobs evaluated.")

                    tailor_agent = ResumeTailorAgent()
                    tailored = tailor_agent.tailor_all_pending_jobs()
                    logger.info(f" Resume tailoring complete: {len(tailored)} tailored PDF resumes generated.")
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

        if path == "/api/clear":
            conn = init_db()
            with conn:
                conn.execute("DELETE FROM application_events")
                conn.execute("DELETE FROM applications")
                conn.execute("DELETE FROM job_matches")
                conn.execute("DELETE FROM resume_versions")
                conn.execute("DELETE FROM jobs")
                conn.execute("DELETE FROM agent_runs")
            conn.close()
            self._send_json({"status": "CLEARED"})
            return

        self.send_response(404)
        self.end_headers()

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

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Dashboard server stopped.")
    finally:
        server.server_close()
