# 🤖 Autonomous AI Job Application Agent

[![CI/CD Pipeline](https://github.com/sasikumarreddychintala/Ai_Job_ApllicationAgent/actions/workflows/ci_cd.yml/badge.svg)](https://github.com/sasikumarreddychintala/Ai_Job_ApllicationAgent/actions/workflows/ci_cd.yml)
[![Live on Render](https://img.shields.io/badge/Render-24%2F7%20Live%20Cloud-success?logo=render)](https://ai-job-apllicationagent.onrender.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](https://docker.com)
[![Telegram Bot](https://img.shields.io/badge/Telegram-1--Tap%20Mobile%20Assistant-2CA5E0?logo=telegram)](https://t.me/SasiJobAlertsBot)
[![Job Boards](https://img.shields.io/badge/Job%20Boards-28%20Parallel%20Adapters-orange?logo=google-cloud)](https://github.com/sasikumarreddychintala/Ai_Job_ApllicationAgent)
[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue?logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

An enterprise-grade, multi-agent career automation platform powered by **28 Concurrent Job Board Adapters**, **Multi-Tier AI Reasoning (Groq Cloud Llama 3.3 70B / Google Gemini 1.5 Flash / Local Ollama)**, **Playwright Browser Automation**, **1-Click Cold Email Dispatcher**, **1-Click LinkedIn Hiring Lead Discovery**, **Dynamic ATS Single-Page Resume Compiler**, and a **24/7 2-Way Mobile Telegram Assistant**.

---

## ⚡ 1-Command Quick Launch

### 💻 Local Run (Laptop):
```bash
python agent.py --ui --port 8000
```
*(On Windows, you can also double-click **`run_dashboard.bat`**)*

Open **`http://localhost:8000`** in your browser!

### ☁️ Cloud Access (24/7 Live Deployment):
* **Web Dashboard:** [https://ai-job-apllicationagent.onrender.com](https://ai-job-apllicationagent.onrender.com)
* **Mobile Telegram Bot:** [@SasiJobAlertsBot](https://t.me/SasiJobAlertsBot)

---

## 📑 Table of Contents
1. [🌟 Key Features & Capabilities](#-key-features--capabilities)
2. [📱 1-Tap Mobile Telegram Assistant](#-1-tap-mobile-telegram-assistant)
3. [🚀 1-Click Free Cloud Deployment (Render + Docker)](#-1-click-free-cloud-deployment-render--docker)
4. [🔒 How to Share with Friends (100% Safe - No Credential Leaks)](#-how-to-share-with-friends-100-safe)
5. [✉️ Gmail SMTP Cold Email & Outreach Setup](#-gmail-smtp-cold-email--outreach-setup)
6. [🛠️ Local Installation Guide](#-local-installation-guide)
7. [🌐 Supported 28 Job Platforms](#-supported-28-job-platforms)
8. [⚙️ Complete `.env` Reference](#-complete-env-reference)

---

## 🌟 Key Features & Capabilities

* 🌐 **28 Parallel Job Board Adapters:** Concurrently discovers active listings across LinkedIn, Naukri, Indeed, Foundit, Wellfound, Unstop, Hasjob, TopHire, YC WorkAtAStartup, Otta, Greenhouse, Lever, Ashby, Remotive, HackerNews, and more in **<20 seconds**!
* 🧠 **Multi-Tier Fault-Tolerant AI Reasoning:**
  * **Tier 1:** Groq Cloud LPU (Llama 3.3 70B Versatile — 500+ tokens/sec)
  * **Tier 2:** Google Gemini Cloud (Gemini 1.5 Flash)
  * **Tier 3:** Local Ollama (Qwen 2.5 / Llama 3 for 100% offline mode)
  * **Tier 4:** Built-in Deterministic Scoring Engine
* 📄 **ATS Single-Page PDF Resume Tailoring:** Dynamically generates pixel-perfect PDF resumes targeting specific job descriptions, inserting missing high-impact technical keywords and computing fit scores.
* 📱 **2-Way Mobile Telegram Assistant:** Control searches, preview tailored PDF resumes, trigger auto-apply, and dispatch cold emails directly from your phone.
* ✉️ **1-Click Cold Email Engine:** Sends personalized recruiter pitches with your tailored PDF resume attached from your verified Gmail address (`smtp.gmail.com:587 TLS / 465 SSL`).
* 📊 **Automated Live Tracker Sync:** Real-time synchronization to Google Sheets and Notion databases upon qualifying or submitting applications.
* 🔐 **Persistent Browser Session Login:** Built-in `python agent.py --login` (`login_session.bat`) opens multi-tab browser sessions to keep your LinkedIn/Naukri logins permanently active.

---

## 📱 1-Tap Mobile Telegram Assistant

The bot provides a persistent **1-Tap Interactive Keyboard** so you never have to type commands manually on mobile:

```text
┌─────────────────────────┬─────────────────────────┐
│     🔥 Top Matches      │      🤖 AI / GenAI      │
├─────────────────────────┼─────────────────────────┤
│     🐍 Python Jobs      │     📊 Data Analyst     │
├─────────────────────────┼─────────────────────────┤
│   🌱 Fresher (0-1 Yr)   │   💼 Junior (1-2 Yrs)   │
├─────────────────────────┼─────────────────────────┤
│      🚀 Auto-Apply      │      ⏰ Follow-ups      │
├─────────────────────────┼─────────────────────────┤
│      📊 Live Stats      │         ⭐ /top         │
└─────────────────────────┴─────────────────────────┘
```

### 📱 Available Telegram Commands:
| Command | Action |
| :--- | :--- |
| **`/start`** | Opens the interactive 1-tap mobile keyboard menu |
| **`/top`** | Delivers Top 5 highest matching qualified jobs with direct apply links |
| **`/fresher [city]`** | Searches high-priority **Fresher & 0–1 Year** openings |
| **`/junior [city]`** | Searches **1–2 Years Experience** & Associate roles |
| **`/ai [city]`** | Searches AI, GenAI, and LLM Engineer roles |
| **`/data [city]`** | Searches Data Analyst and BI Developer roles |
| **`/resume <job_id>`** | Compiles & uploads your tailored single-page PDF resume to the chat |
| **`/email <job_id> hr@company.com`** | Dispatches a cold email with your tailored PDF resume attached |
| **`/apply <job_id>`** | Launches Playwright browser auto-pilot to fill the job form |
| **`/autoapply`** | Runs auto-apply across all $\ge 80\%$ qualified jobs |
| **`/prep <job_id>`** | Predicts Top 5 technical interview questions with STAR answers |
| **`/hiring <job_id>`** | Generates direct search links for Engineering Managers on LinkedIn |
| **`/followups`** | Shows jobs eligible for polite 3/7-day recruiter follow-ups |
| **`/stats`** | Displays pipeline metrics (Discovered, Qualified, Submitted) |

---

## 🚀 1-Click Free Cloud Deployment (Render + Docker)

Host your agent 24/7/365 in the cloud for **$0.00** forever:

1. **Fork** or connect this repository to **[Render.com](https://dashboard.render.com)**.
2. Click **`New +`** ➡️ **`Web Service`** ➡️ Select your repository.
3. Choose **`Docker`** as the Environment.
4. Select **`Free`** tier.
5. In **Environment Variables**, paste your secret keys:
   * `GROQ_API_KEY`: *(Get free at [console.groq.com](https://console.groq.com/keys))*
   * `TELEGRAM_BOT_TOKEN`: *(From Telegram `@BotFather`)*
   * `TELEGRAM_CHAT_ID`: *(Your numeric ID)*
   * `SMTP_USER`: `your_email@gmail.com`
   * `SMTP_PASSWORD`: *(Your 16-char Google App Password)*
   * `HEADLESS`: `true`
6. Click **Create Web Service**!
7. *(Optional)* Add your Render URL to **[UptimeRobot](https://uptimerobot.com)** with a 5-minute HTTP monitor on `/healthz` to keep your free instance awake 24/7!

---

## 🔒 How to Share with Friends (100% Safe)

You can safely share this repository with friends or colleagues without exposing your private credentials:

1. **Why Your Data is Protected:**
   * Your API keys, passwords, and tokens live strictly in **`.env`** (which is in `.gitignore` and never committed).
   * Your saved browser cookies and login sessions are in **`data/logs/browser_context/`** (gitignored).
   * Your PDF resumes and SQLite database are in **`data/`** (gitignored).

2. **How Friends Can Run Their Own Copy:**
   * Tell your friends to **`Fork`** this repository to their GitHub account.
   * They copy `.env.example` to `.env` and add **their own** API keys.
   * They open the Web UI at `http://localhost:8000` (or deploy to Render) and enter their own name, skills, and experience in the **Profile Manager**!

---

## ✉️ Gmail SMTP Cold Email & Outreach Setup

To enable 1-click cold emailing and recruiter outreach:

1. Go to your **Google Account** ➡️ **Security** ➡️ Enable **2-Step Verification**.
2. Search for **App Passwords** ➡️ Create a new App Password named `"Job Agent"`.
3. Copy the generated 16-character password (e.g. `abcd efgh ijkl mnop`).
4. Set in your `.env`:
   ```env
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=abcd efgh ijkl mnop
   SMTP_FROM_NAME="Your Name"
   ```

---

## 🛠️ Local Installation Guide

### 1. Clone & Setup
```bash
git clone https://github.com/sasikumarreddychintala/Ai_Job_ApllicationAgent.git
cd Ai_Job_ApllicationAgent
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -U pip setuptools wheel
pip install -r requirements.txt
playwright install --with-deps chromium
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your Groq, Telegram, and Gmail credentials
```

### 4. Launch Dashboard
```bash
python agent.py --ui --port 8000
```

---

## 🌐 Supported 28 Job Platforms

| Category | Platforms Supported |
| :--- | :--- |
| **Enterprise & Direct ATS** | Greenhouse, Lever, Ashby, Workable, SmartRecruiters |
| **India & Tech Hub Portals** | LinkedIn India, Naukri, Indeed India, Foundit (Monster), Hasjob, TopHire, Unstop |
| **Startups & High Growth** | Wellfound (AngelList), YC WorkAtAStartup, Instahyre, Cutshort, Hirist |
| **Global & Remote** | Remotive, RemoteOK, HackerNews Who's Hiring, Himalayas, Jobicy, WeWorkRemotely, Otta, Turing, AIJobs.net, Python.org Jobs |

---

## ⚙️ Complete `.env` Reference

```env
# ==============================================================================
# 🧠 AI REASONING ENGINES
# ==============================================================================
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
GEMINI_API_KEY=AIza...
GEMINI_MODEL=gemini-1.5-flash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b-instruct

# ==============================================================================
# 📱 MOBILE ASSISTANT (Telegram & Discord)
# ==============================================================================
TELEGRAM_BOT_TOKEN=8764265758:...
TELEGRAM_CHAT_ID=6230874116
TELEGRAM_MIN_SCORE=80
DISCORD_WEBHOOK_URL=

# ==============================================================================
# 📬 1-CLICK COLD EMAIL DISPATCHER (Gmail SMTP)
# ==============================================================================
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
SMTP_FROM_NAME="Your Name"

# ==============================================================================
# 📊 LIVE TRACKERS (Google Sheets & Notion)
# ==============================================================================
GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/.../exec
NOTION_API_KEY=
NOTION_DATABASE_ID=

# ==============================================================================
# ⚙️ APPLICATION & BROWSER AUTOMATION SETTINGS
# ==============================================================================
RESUME_THEME=tech
HEADLESS=true
DAILY_APPLICATION_LIMIT=20
INSPECTION_PAUSE_SECONDS=180
```

---

## 📄 License
Distributed under the **MIT License**. See `LICENSE` for more information.
