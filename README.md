# 🤖 Personal AI Job Application Agent

A local-first, zero-paid-API autonomous job application agent powered by **Python**, **Ollama (`qwen2.5:7b-instruct`)**, **Playwright**, and **SQLite / PostgreSQL**.

---

## ⚡ The 1-Command Quick Start

To launch the full web application immediately:
```bash
python agent.py --ui --port 8000
```
*(On Windows, you can also just double-click **`run_dashboard.bat`**)*

Open **`http://localhost:8000`** in your browser!

---

## 📑 Table of Contents
1. [Prerequisites](#-prerequisites)
2. [Step-by-Step Installation Guide (For New Clones)](#-step-by-step-installation-guide)
3. [How to Use the Web Dashboard (100% GUI)](#-how-to-use-the-web-dashboard)
4. [Supported Job Boards & Platforms](#-supported-job-boards--platforms)
5. [CLI Command Reference (For Terminal Users)](#-cli-command-reference)
6. [Database Configuration (SQLite vs PostgreSQL)](#-database-configuration)
7. [Architecture & Safety Guardrails](#-architecture--safety-guardrails)
8. [Troubleshooting & FAQs](#-troubleshooting--faqs)

---

## 🛠 Prerequisites

Before running the project, ensure you have the following installed on your system:

1. **Python 3.10 to 3.13** ([Download Python](https://www.python.org/downloads/))
2. **Ollama** ([Download Ollama](https://ollama.com/download)) for local, privacy-first AI.
3. **Git** ([Download Git](https://git-scm.com/))

---

## 🚀 Step-by-Step Installation Guide

Follow these steps to set up and run the repository on any computer:

### 1. Clone the Repository
```bash
git clone <YOUR_REPOSITORY_URL>
cd Job_Application_Agent
```

### 2. Create and Activate a Virtual Environment
```bash
# Windows (PowerShell / Command Prompt):
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux:
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install Playwright Chromium Browser
```bash
playwright install chromium
```

### 5. Pull & Start the Local AI Model (Ollama)
Open a terminal and run:
```bash
# Pull the recommended fast 7B reasoning model:
ollama pull qwen2.5:7b-instruct

# Start Ollama service (if not already running):
ollama serve
```

### 6. Set Up Environment Variables (Optional)
The project comes with working defaults. You can optionally create your `.env` file:
```bash
# Windows:
copy .env.example .env

# macOS / Linux:
cp .env.example .env
```

---

## 🌟 How to Use the Web Dashboard

### Step 1: Start the Dashboard
```bash
python agent.py --ui --port 8000
```
*(or double-click `run_dashboard.bat`)*

Navigate to **`http://localhost:8000`** in your web browser.

### Step 2: Upload Your Resume (1-Click)
* Click the **"📄 Upload Resume"** button in the top right.
* Select your `.pdf` or `.docx` resume file.
* The agent's local AI will instantly extract your verified contact details, skills, projects, and work experience.

### Step 3: Search & Score Jobs (1-Click)
* Enter your target **Job Title** (e.g. `Python Developer`, `Backend Engineer`, `FastAPI Developer`).
* Enter your target **Location** (e.g. `Bengaluru`, `Remote`, `Hyderabad`).
* Choose your **Recency Filter** (`Past 24 Hours`, `Past 3 Days`, or `Past 7 Days`).
* Click **"⚡ Search & Score Match"**.

The agent automatically:
1. Scrapes live job postings across top platforms.
2. Analyzes job requirements with Ollama.
3. Calculates your **7-Factor Match Score** (e.g. `90/100`, `83/100`) against your resume and experience.
4. Renders the color-coded results in the live table.

### Step 4: Review & Auto-Apply
* Check **"Show Only Qualified Jobs (≥ 70 Score)"** to filter out low-fit openings.
* Click **"View Job ↗"** on any row to open the live job link.
* Click **"🚀 Auto-Apply to All Qualified"** to launch Playwright browser automation with ATS-tailored PDF resumes.

---

## 🌟 Key Features

* **⚡ 1-Click Search & 100-Point Match Scoring**: Evaluates tech stack, experience duration, and project fit against your master resume across 10+ platforms simultaneously in ~3 seconds.
* **🌐 High-Shortlisting & Low-Competition Job Feeds**: Ashby Direct ATS (*Cursor, ElevenLabs, Replit, Perplexity*), Hacker News "Who is Hiring" (YC), Python.org, Greenhouse/Lever, LinkedIn, Jobicy, Himalayas, Remotive.
* **📬 1-Click Recruiter Cold Outreach & LinkedIn Note Generator**: Generates sub-300-character personalized LinkedIn connection request notes, hiring manager cold emails, and recruiter InMails tailored to the specific role.
* **📝 Automated Tailored Cover Letter Generator (PDF & Text)**: Compiles professional ReportLab PDF cover letters emphasizing real candidate metrics (e.g. 30% latency reduction).
* **🧠 AI Interview Prep & Question Predictor**: Predicts the Top 10 technical & system design interview questions for the target job + STAR-method talking points based on your verified background.
* **⏰ Automated Morning Auto-Pilot (Hands-Free)**: Runs full job discovery, scoring, and tailored PDF generation daily at 8:00 AM while you sleep without typing any commands.
* **📱 100% Free Mobile Push Notifications (Telegram & Discord)**: Sends instant phone push alerts whenever a 90%+ match is discovered from low-competition boards + morning application digests.

---

## ⏰ Hands-Free Morning Auto-Pilot (Windows Task Scheduler)

You can run the entire job discovery, matching, and resume tailoring pipeline completely hands-free every morning at **08:00 AM** — even with your laptop lid closed!

### ⏱️ 1-Minute Setup (Do this once):
1. Open File Explorer to:
   ```text
   C:\Users\heman\Documents\Job_Application_Agent\scripts\
   ```
2. **Right-click `setup_windows_scheduler.bat`** and click **Run as administrator**.
3. It registers the Windows scheduled task with **`Wake-To-Run`** enabled.

### 💤 What Happens Automatically Every Morning:
* If your laptop is in **Sleep / Standby mode** (closed lid with charger connected), Windows will automatically **wake up at 8:00 AM**.
* Scrapes 100+ new jobs across all 10+ platforms.
* Evaluates match fit against your master resume.
* Compiles tailored PDF resumes into `data/tailored_resumes/`.
* Sends an instant **Telegram push alert** to your phone with top 90%+ matches and your daily digest.
* Automatically puts the laptop back to sleep.

---

## 📱 Telegram Mobile Push Notifications Setup (100% Free Forever)

Receive instant mobile notifications whenever a **90%+ match job** is posted from low-competition boards (*Ashby, Hacker News, Python.org, Direct ATS*).

### ⏱️ 30-Second Setup:
1. Open Telegram and search for **`@BotFather`** (official Telegram bot creator).
2. Send: `/newbot` and follow the prompts to create your bot name and username.
3. BotFather will provide your **Telegram Bot Token** (e.g. `8764265758:AAFhY...`).
4. Search for your new bot in Telegram and click **`Start`** (or send any message).
5. Search for **`@userinfobot`** in Telegram and click Start — it will reply with your numeric **Chat ID** (e.g. `6230874116`).
6. Open your Job Agent dashboard (`http://localhost:8000`), click **`🔔 Alerts Setup`**, paste your **Bot Token** and **Chat ID**, and click **`💾 Save Credentials`**.
7. Click **`🧪 Send Test Alert`** to receive a test message on your phone!

---

## 🌐 Supported Job Boards & Platforms (10+ High-Conversion Sources)

| Platform | Type | Highlights & Advantages |
| :--- | :--- | :--- |
| **⭐ Ashby Direct ATS** | Modern Scaleup ATS | **Lowest bot competition & direct engineering hiring** (Cursor, ElevenLabs, Replit, Perplexity, Ramp, Retool) |
| **🔥 Hacker News (YC)** | Direct Founder / Engineering Lead | **100% Genuine YC & startup founder postings** directly from "Who is Hiring?" threads with zero recruiter intermediaries |
| **★ Python.org (Official)** | Low-Competition Community Feed | **Official Python Software Foundation postings** with 3x–5x higher interview response rates |
| **🚀 Cutshort** | Indian Startup Hiring | **Direct connection to Founders, CTOs & Engineering Leads** in Bengaluru with rapid response times |
| **⚡ Instahyre** | Premium Indian Tech Board | **Curated AI-matched software roles** with high-intent tech recruiters in Bengaluru & Hyderabad |
| **💎 Hirist** | Specialized Indian Tech Portal | **Curated backend, python, and distributed systems jobs** across top product companies |
| **🌐 Indeed India** | High Volume Tech Search | **Live developer and backend listings** across Bengaluru, Hyderabad, and Remote |
| **⚡ Greenhouse & Lever** | Direct Enterprise ATS | **Direct company application portals** (Supabase, Linear, Postman, Anthropic, Figma, Razorpay, Cred) |
| **LinkedIn** | Public Job Search | Live scraping with real-time 24h/3d recency filters |
| **Jobicy** | Remote Tech Board | High-signal, low-competition remote developer roles |
| **Himalayas** | Modern Remote Tech | Verified remote software engineering positions |
| **We Work Remotely** | Curated Tech Feeds | High-quality backend, python, and full-stack listings |
| **Remotive** | Curated Developer Board | Hand-screened engineering listings with verified salaries |
| **Naukri India** | Tech Job Search | Top Indian IT openings in Bengaluru, Hyderabad, etc. |
| **RemoteOK** | Tech Remote Board | Filtered developer openings worldwide |

---

## 💻 CLI Command Reference

If you prefer running commands from the terminal instead of the web dashboard:

```bash
# 1. Check system and environment health:
python agent.py --check

# 2. Import a resume file:
python agent.py --import-resume "data/master_resume/resume.pdf"

# 3. Discover live jobs with recency filters:
python agent.py --discover-jobs --search "Python Backend" --location "Bengaluru" --time-range 24h

# 4. Analyze requirements with local LLM:
python agent.py --analyze-jobs

# 5. Evaluate 7-factor match scores:
python agent.py --match-jobs

# 6. Generate ATS-tailored PDF resumes for qualified jobs:
python agent.py --tailor-resumes

# 7. Run autonomous Playwright browser applications (dry-run safe):
python agent.py --run-agent

# 8. Target a single job URL directly:
python agent.py --apply-url "https://job-url.com" [--live]

# 9. View application tracking history:
python agent.py --show-history

# 10. Export audit history:
python agent.py --export-audit json
```

---

## 🗄 Database Configuration

### SQLite (Default)
Zero-configuration required. All application state is stored locally in `data/applications.db`.

### PostgreSQL
To switch to PostgreSQL:
1. Ensure your PostgreSQL instance is running.
2. In `.env`, set:
   ```env
   DATABASE_TYPE=postgres
   DATABASE_URL=postgresql://postgres:password@localhost:5432/job_agent
   ```
The agent automatically creates and manages all relational tables on startup.

---

## 🛡 Architecture & Safety Guardrails

* **Zero Hallucination Policy**: The agent formulates answers strictly from verified facts in `data/candidate_profile.json`. If a question asks for unknown details, it halts with `MANUAL_ACTION_REQUIRED` instead of fabricating answers.
* **Safety Inspection Mode (`DRY_RUN=true`)**: Fills the entire application form and stops right before the final submission button, allowing you to review all inputs.
* **Human-in-the-Loop (HITL) for CAPTCHAs**: When a CAPTCHA appears, the agent pauses, rings an alert, keeps the browser open for you to solve, and resumes automatically once cleared.
* **ATS Resume Versioning**: Tailored derivative PDFs are compiled per job with relevant keywords into `data/tailored_resumes/` while strictly preserving truthful candidate facts.

---

## ❓ Troubleshooting & FAQs

**Q: Ollama connection timed out or connection refused?**
* Ensure Ollama is running: run `ollama serve` in a separate terminal and verify `ollama list` shows `qwen2.5:7b-instruct`.

**Q: Browser closes immediately?**
* The default setting is `HEADLESS=false` with human inspection pause. You can adjust `SLOW_MO=500` in `.env`.

**Q: How do I run automated tests?**
* Run `python -m pytest` to execute the full 43-test suite across all modules.

---

## 📄 License
MIT License. Built for ethical, local-first, privacy-preserving autonomous job application assistance.
