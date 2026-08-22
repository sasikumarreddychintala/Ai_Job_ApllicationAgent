# System Configuration Specification (Phase 0)

## Configuration Overview
The Personal AI Job Application Agent utilizes environment variables (`.env`) parsed via `pydantic-settings` in `config.py`.

## Configuration Schema & Options

```ini
# --- Application Execution Options ---
ENV=development                          # development | production | testing
DRY_RUN=true                             # If true, populates form but stops before clicking Submit
DAILY_APPLICATION_LIMIT=10               # Maximum applications to process per day
LOG_LEVEL=INFO                           # DEBUG | INFO | WARNING | ERROR

# --- Target Candidate Criteria ---
MIN_MATCH_SCORE=70                       # Minimum score threshold (0-100) to qualify a job
PREFERRED_LOCATIONS=["Remote", "Hybrid"]
JOB_ROLES=["Software Engineer", "Full Stack Engineer", "Python Developer", "AI Engineer"]

# --- Ollama Local LLM Settings ---
OLLAMA_BASE_URL=http://localhost:11434   # Local Ollama service endpoint
OLLAMA_MODEL=llama3.2                    # Local LLM model name (e.g. llama3.2, qwen2.5:7b, mistral)
OLLAMA_TIMEOUT=60                        # Timeout in seconds for LLM calls

# --- Browser & Playwright Settings ---
HEADLESS=false                           # Must be false for visual monitoring & CAPTCHA handling
SLOW_MO=500                              # Delay in milliseconds between Playwright actions
BROWSER_TIMEOUT=30000                    # Page timeout in milliseconds

# --- Local File System Paths ---
DATABASE_PATH=data/applications.db
MASTER_RESUME_PATH=data/master_resume/resume.pdf
CANDIDATE_PROFILE_PATH=data/candidate_profile.json
TAILORED_RESUMES_DIR=data/tailored_resumes/
LOGS_DIR=data/logs/
```
