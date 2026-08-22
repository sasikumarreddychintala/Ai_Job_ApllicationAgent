# 🤖 Personal AI Job Application Agent

An autonomous, multi-agent career automation platform powered by **28 Parallel Job Board Adapters**, **Multi-Tier AI Engine (Groq 70B / Google Gemini / Ollama)**, **Playwright Browser Automation**, **Dynamic ATS-Tailored PDF Resumes**, and a **2-Way Interactive Telegram Assistant**.

---

## ⚡ 1-Command Quick Start

To launch the full web application immediately:
```bash
python agent.py --ui --port 8000
```
*(On Windows, you can also double-click **`run_dashboard.bat`**)*

Open **`http://localhost:8000`** in your browser!

---

## 📑 Table of Contents
1. [🌟 Features & Capabilities](#-features--capabilities)
2. [🛠️ Prerequisites & Installation](#-prerequisites--installation)
3. [🧠 AI Engine Configuration (Groq vs Gemini vs Ollama)](#-ai-engine-configuration)
4. [📱 Telegram Bot Setup & Mobile Control](#-telegram-bot-setup--mobile-control)
5. [📊 Google Sheets & Notion Tracker Setup](#-google-sheets--notion-tracker-setup)
6. [✉️ Gmail SMTP Cold Email Outreach Setup](#-gmail-smtp-cold-email-outreach-setup)
7. [⏰ 24/7 Automated Cloud Scout (GitHub Actions)](#-247-automated-cloud-scout-github-actions)
8. [🐳 Docker & Oracle Cloud Always Free Deployment](#-docker--oracle-cloud-always-free-deployment)
9. [🌐 Supported 28 Job Platforms](#-supported-28-job-platforms)
10. [⚙️ Complete `.env` Reference](#-complete-env-reference)

---

## 🌟 Features & Capabilities

* 🌐 **28 Concurrent Job Boards:** Scrapes LinkedIn, Unstop, Hasjob, TopHire, Foundit, YC Startups, Indeed, Wellfound, Otta, AIJobs.net, Turing, Ashby, and more in **<25 seconds**!
* 🧠 **Multi-Tier Fault-Tolerant AI:** Auto-failover from **Groq (Llama 3.3 70B)** ➡️ **Google Gemini 1.5 Flash** ➡️ **Local Ollama** ➡️ **Deterministic Rule Engine**.
* 📄 **ATS-Beating Tailored PDF Resumes:** Automatically injects missing keywords, aligns experience periods, and outputs single-page ATS PDFs with clickable portfolio links.
* 📱 **2-Way Mobile Assistant on Telegram:** Control the entire system from your phone (`/search`, `/fresher`, `/ai`, `/data`, `/top`, `/resume`, `/prep`).
* ✉️ **1-Click Cold Email Outreach:** Dispatches personalized recruiter pitches with tailored PDF resumes attached from your real Gmail.
* 📊 **Live Tracker Sync:** Automatically pushes evaluated jobs ($\ge 70\%$) to Google Sheets and Notion.

---

## 🛠️ Prerequisites & Installation

### 1. Clone Repository
```bash
git clone https://github.com/sasikumarreddychintala/Ai_Job_ApllicationAgent.git
cd Job_Application_Agent
```

### 2. Create Virtual Environment
```bash
# Windows
python -m venv venv
.env\Scriptsctivate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 4. Create Your `.env` File
```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

---

## 🧠 AI Engine Configuration

The agent features an **automatic multi-tier AI failover system**. Choose what works best for you:

```text
┌────────────────────────────────────────────────────────┐
│ 🥇 TIER 1: Groq Cloud (Llama 3.3 70B - 0.2s ultra-fast)│
└──────────────────────────┬─────────────────────────────┘
                           │ (If Rate-Limited / 429)
                           ▼
┌────────────────────────────────────────────────────────┐
│ 🥈 TIER 2: Google Gemini Cloud (Gemini 1.5 Flash)      │
└──────────────────────────┬─────────────────────────────┘
                           │ (If Rate-Limited / Quota)
                           ▼
┌────────────────────────────────────────────────────────┐
│ 🥉 TIER 3: Local Ollama (Qwen 2.5 - Offline)          │
└──────────────────────────┬─────────────────────────────┘
                           │ (If Offline)
                           ▼
┌────────────────────────────────────────────────────────┐
│ 🛡️ TIER 4: Built-in Deterministic Rule Engine          │
└────────────────────────────────────────────────────────┘
```

### Option A: Groq Cloud (Recommended — Ultra-Fast 0.2s & Free)
1. Get a free API key at **[console.groq.com/keys](https://console.groq.com/keys)** (No credit card required).
2. Add to `.env`:
   ```env
   GROQ_API_KEY=gsk_your_groq_api_key_here
   GROQ_MODEL=llama-3.3-70b-versatile
   ```

### Option B: Google Gemini Cloud (Free 1.5 Flash)
1. Get a free API key at **[aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)**.
2. Add to `.env`:
   ```env
   GEMINI_API_KEY=AIzaSy_your_gemini_api_key_here
   GEMINI_MODEL=gemini-1.5-flash
   ```

### Option C: 100% Offline Local AI (Ollama)
1. Install Ollama from **[ollama.com](https://ollama.com)**.
2. Pull the model:
   ```bash
   ollama pull qwen2.5:3b-instruct
   ```
3. Add to `.env`:
   ```env
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=qwen2.5:3b-instruct
   ```

---

## 📱 Telegram Bot Setup & Mobile Control

Receive instant job match alerts and control the entire agent from your phone via Telegram!

### 1. Create Your Telegram Bot
1. Open Telegram and search for **`@BotFather`**.
2. Send `/newbot`, choose a name and username (e.g. `MyJobAlertsBot`).
3. Copy the **HTTP API Token** (e.g. `7891234567:AAHxyz...`).

### 2. Get Your Personal Chat ID
1. In Telegram, search for **`@userinfobot`** (or `@GetIDsBot`).
2. Send `/start` — it will reply with your numeric **Id** (e.g. `1234567890`).

### 3. Add to `.env`:
```env
TELEGRAM_BOT_TOKEN=7891234567:AAHxyz...
TELEGRAM_CHAT_ID=1234567890
TELEGRAM_MIN_SCORE=80
```

### 📱 Available Telegram Commands:
* `/search Python Developer Bengaluru` ➡️ Searches 28 boards & scores matches
* `/fresher Bengaluru` ➡️ Hunts 0–1 Year entry-level openings
* `/junior Bengaluru` ➡️ Hunts 1–2 Years associate openings
* `/ai` or `/genai` ➡️ Searches AI, LLM, LangChain, and RAG roles
* `/data` ➡️ Searches Data Analyst & Analytics roles
* `/backend` or `/swe` ➡️ Searches Software Engineering & Python Backend roles
* `/top` ➡️ Shows top 5 scored job openings with direct apply links
* `/resume <job_id>` ➡️ Compiles ATS PDF resume and **downloads it directly in your chat**!
* `/prep <job_id>` ➡️ Generates custom **STAR-format interview answers**
* `/email <job_id> <email>` ➡️ Sends 1-click cold email with resume attached
* `/sync` ➡️ Pushes qualified jobs to Google Sheets / Notion
* `/stats` ➡️ Shows live database metrics

---

## 📊 Google Sheets & Notion Tracker Setup

### Option 1: Free Google Sheets Webhook Sync
1. Open a new Google Sheet and go to **Extensions ➡️ Apps Script**.
2. Paste this script:
   ```javascript
   function doPost(e) {
     var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
     var data = JSON.parse(e.postData.contents);
     sheet.appendRow([new Date(), data.company, data.title, data.location, data.score, data.url, data.status]);
     return ContentService.createTextOutput("SUCCESS");
   }
   ```
3. Click **Deploy ➡️ New Deployment** ➡️ Select **Web App** ➡️ Set Access to **"Anyone"**.
4. Copy the Webhook URL and add to `.env`:
   ```env
   GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/.../exec
   ```

### Option 2: Notion Database Sync
1. Create an integration at **[notion.so/my-integrations](https://www.notion.so/my-integrations)** and get your **Internal Integration Token**.
2. Create a Notion Database with columns: `Company`, `Role`, `Location`, `Match Score`, `Status`, `Job URL`.
3. Share the database with your integration and copy the Database ID from the URL.
4. Add to `.env`:
   ```env
   NOTION_API_KEY=secret_...
   NOTION_DATABASE_ID=...
   ```

---

## ✉️ Gmail SMTP Cold Email Outreach Setup

Bypass the ATS queue by emailing Founders and Engineering Managers directly from your Gmail with your tailored PDF resume attached:

1. Go to your Google Account: **[myaccount.google.com/security](https://myaccount.google.com/security)**.
2. Enable **2-Step Verification**.
3. Search for **"App passwords"** in the top search bar.
4. Create an App Password called `JobAgent` and copy the **16-letter password**.
5. Add to `.env`:
   ```env
   SMTP_SERVER=smtp.gmail.com
   SMTP_PORT=587
   SMTP_USER=your_email@gmail.com
   SMTP_PASSWORD=abcd efgh ijkl mnop
   SMTP_FROM_NAME="Your Name"
   ```

---

## ⏰ 24/7 Automated Cloud Scout (GitHub Actions)

Run the agent on GitHub's cloud servers twice daily (**8:00 AM & 2:00 PM IST**) for **$0.00** without keeping your laptop on:

1. Push this repository to your private GitHub.
2. Go to **Settings ➡️ Secrets and variables ➡️ Actions**.
3. Add your secrets:
   * `TELEGRAM_BOT_TOKEN`
   * `TELEGRAM_CHAT_ID`
   * `GROQ_API_KEY` *(or `GEMINI_API_KEY`)*
   * `SMTP_USER` & `SMTP_PASSWORD` *(optional for email outreach)*
4. Test run anytime under the **Actions** tab ➡️ **`🤖 24/7 AI Job Hunter & Telegram Dispatcher`** ➡️ **Run workflow**!

---

## 🐳 Docker & Oracle Cloud Always Free Deployment

Deploy on an **Oracle Cloud Always Free VM (4 OCPUs, 24 GB RAM, 200 GB Storage)** forever for **$0.00**:

```bash
# 1. Clone repository on your VM
git clone https://github.com/sasikumarreddychintala/Ai_Job_ApllicationAgent.git
cd Job_Application_Agent

# 2. Configure environment
cp .env.example .env
nano .env

# 3. Start Docker stack
docker compose up -d --build

# 4. Pull lightweight AI model into local container
docker exec -it agent-ollama ollama pull qwen2.5:3b-instruct
```

---

## 🌐 Supported 28 Job Platforms

| Category | Platforms |
| :--- | :--- |
| 🇮🇳 **India & Tech Hubs** | **Unstop**, **Hasjob**, **Foundit (Monster)**, **TopHire**, **Cutshort**, **Instahyre**, **Hirist**, **Hirect**, **Internshala**, **Naukri** |
| 🚀 **YC & High-Growth AI** | **YC WorkAtAStartup**, **AIJobs.net**, **Otta**, **Wellfound (AngelList)**, **Turing**, **Ashby** |
| 🌐 **Global & Remote** | **LinkedIn**, **Indeed**, **Python.org**, **Jobicy**, **WeWorkRemotely**, **Himalayas**, **RemoteOK**, **Remotive**, **Arbeitnow**, **Hacker News** |
| 🏢 **Enterprise ATS** | **Greenhouse**, **Lever** |

---

## ⚙️ Complete `.env` Reference

```env
# Application Settings
ENV=production
HEADLESS=true
DRY_RUN=true
MIN_MATCH_SCORE=70
LOG_LEVEL=INFO

# AI Providers (Groq -> Gemini -> Ollama Fallback)
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama-3.3-70b-versatile
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-1.5-flash
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:3b-instruct

# Telegram Bot (Mobile Control & Alerts)
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
TELEGRAM_MIN_SCORE=80

# Cold Email Outreach (Gmail SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=your_16_char_app_password
SMTP_FROM_NAME="Your Name"

# Live Trackers (Google Sheets & Notion)
GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/.../exec
NOTION_API_KEY=secret_...
NOTION_DATABASE_ID=...
```

---

## 📜 License
MIT License. Built for autonomous developer job hunting & career acceleration. 🚀
