import os
from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Environment & Operations
    BASE_DIR: Path = BASE_DIR
    ENV: str = "development"
    DRY_RUN: bool = True
    DAILY_APPLICATION_LIMIT: int = 50
    MIN_MATCH_SCORE: int = 70
    CUSTOM_EXPERIENCE_ALIGNMENT: bool = True
    RESUME_THEME: str = "tech"
    LOG_LEVEL: str = "INFO"

    # Database Configuration (sqlite or postgres)
    DATABASE_TYPE: str = "sqlite"
    DATABASE_URL: str = ""

    # Multi-Tier Cloud & Local AI Configuration (Groq -> Gemini -> Ollama Fallback)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b-instruct"
    OLLAMA_TIMEOUT: int = 60
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Playwright Browser Configuration
    HEADLESS: bool = False
    SLOW_MO: int = 50
    BROWSER_TIMEOUT: int = 25000
    INSPECTION_PAUSE_SECONDS: int = 35

    # Mobile & Chatbot Notifications (Telegram, Discord)
    TELEGRAM_BOT_TOKEN: str = ""
    TELEGRAM_CHAT_ID: str = ""
    TELEGRAM_MIN_SCORE: int = 80
    DISCORD_WEBHOOK_URL: str = ""

    # Cold Email & Direct Outreach SMTP Configuration (Gmail, Outlook, Custom)
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "Sasi Kumar Reddy Chintala"

    # Live Application Tracker Sync (Google Sheets Webhook & Notion API)
    GOOGLE_SHEETS_WEBHOOK_URL: str = ""
    NOTION_API_KEY: str = ""
    NOTION_DATABASE_ID: str = ""

    # File Paths
    DATABASE_PATH: Path = BASE_DIR / "data" / "applications.db"
    MASTER_RESUME_PATH: Path = BASE_DIR / "data" / "master_resume" / "resume.pdf"
    CANDIDATE_PROFILE_PATH: Path = BASE_DIR / "data" / "candidate_profile.json"
    TAILORED_RESUMES_DIR: Path = BASE_DIR / "data" / "tailored_resumes"
    LOGS_DIR: Path = BASE_DIR / "data" / "logs"

    def ensure_directories(self):
        """Creates required system directories if they do not exist."""
        self.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.MASTER_RESUME_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.TAILORED_RESUMES_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)

settings = Settings()
settings.ensure_directories()
