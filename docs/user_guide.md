# 📖 Personal AI Job Application Agent — User & Developer Guide

This guide provides everything needed to run, customize, and deploy the agent.

---

## ⚡ The 1-Command Run

```bash
python agent.py --ui --port 8000
```
*(On Windows: double-click **`run_dashboard.bat`**)*

Open **`http://localhost:8000`** in your browser.

---

## 🚀 Setup for New Users / Cloned Repositories

### Step 1: Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 2: Install Requirements & Playwright
```bash
pip install -r requirements.txt
playwright install chromium
```

### Step 3: Start Ollama (Local AI Model)
```bash
ollama pull qwen2.5:7b-instruct
ollama serve
```

### Step 4: Launch Web Dashboard
```bash
python agent.py --ui --port 8000
```

---

## 🌐 Web Dashboard Workflows

1. **Upload Resume**: Click **"📄 Upload Resume"** to parse your `.pdf` or `.docx` resume into verified candidate facts.
2. **Search & Score**: Type your keywords (e.g. `Python Developer`), select location (`Bengaluru`, `Remote`), choose recency (`Past 24 Hours`, `Past 3 Days`), and click **"⚡ Search & Score Match"**.
3. **Auto-Apply**: Click **"🚀 Auto-Apply to All Qualified"** to let Playwright open the browser and complete application forms.
