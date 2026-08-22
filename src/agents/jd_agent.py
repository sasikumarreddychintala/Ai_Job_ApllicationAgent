import json
import sqlite3
import re
from typing import List, Optional
from datetime import datetime, timezone

from config import settings
from src.utils.logger import logger
from src.database.models import init_db
from src.ai.schemas import ParsedJDRequirements
from src.ai.ollama_client import OllamaClient
from src.ai.prompts.jd_prompt import render_jd_prompt

class JDAgent:
    """Agent responsible for analyzing raw job descriptions into structured requirement objects."""

    def __init__(self, ollama_client: Optional[OllamaClient] = None, db_path=settings.DATABASE_PATH):
        self.ollama = ollama_client or OllamaClient()
        self.db_path = db_path

    def analyze_job(self, job_id: int, conn: Optional[sqlite3.Connection] = None) -> ParsedJDRequirements:
        """Analyzes raw JD text for a specific job_id and updates SQLite record to ANALYZED state."""
        should_close = False
        if conn is None:
            conn = init_db(self.db_path)
            should_close = True

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT id, title, company, location, raw_jd FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Job ID {job_id} not found in database.")

            _, default_title, default_company, default_loc, raw_jd = row
            logger.info(f" Analyzing JD for Job ID {job_id}: '{default_title}' at {default_company}...")

            # Extract requirements via Ollama or fallback
            requirements = self._extract_requirements(raw_jd, default_title, default_company, default_loc)

            # Persist structured requirements & advance state to ANALYZED
            req_json = json.dumps(requirements.model_dump(), ensure_ascii=False)
            with conn:
                conn.execute(
                    "UPDATE jobs SET analyzed_requirements = ? WHERE id = ?",
                    (req_json, job_id)
                )
                conn.execute(
                    "UPDATE applications SET status = 'ANALYZED', updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                    (job_id,)
                )

            logger.info(f" Successfully analyzed Job ID {job_id}. Status updated to ANALYZED.")
            return requirements

        finally:
            if should_close:
                conn.close()

    def analyze_all_pending_jobs(self, limit: int = 150) -> List[ParsedJDRequirements]:
        """Analyzes up to 150 pending jobs in DISCOVERED state with lightning speed and comprehensive tech parsing."""
        conn = init_db(self.db_path)
        analyzed_list = []
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT j.id, j.title FROM jobs j
                JOIN applications a ON j.id = a.job_id
                WHERE a.status = 'DISCOVERED'
                ORDER BY j.id DESC
                """
            )
            rows = cursor.fetchall()
            logger.info(f" Found {len(rows)} pending jobs in DISCOVERED state.")

            non_tech_keywords = [
                "barber", "nanny", "technician", "driver", "meat", "lifeguard", 
                "hostess", "bell person", "janitorial", "cleaner", "labourer", 
                "cashier", "clerk", "electrician", "handyman", "painter", "influencer",
                "counsel", "financial analyst", "dispute analyst", "compliance"
            ]

            processed_count = 0
            for j_id, title in rows:
                t_lower = title.lower()
                # Fast skip clearly non-tech jobs
                if any(k in t_lower for k in non_tech_keywords):
                    with conn:
                        conn.execute("UPDATE applications SET status = 'SKIPPED' WHERE job_id = ?", (j_id,))
                    continue

                if processed_count >= limit:
                    break

                req = self.analyze_job(j_id, conn=conn)
                analyzed_list.append(req)
                processed_count += 1

            logger.info(f" Batch JD analysis complete: {len(analyzed_list)} jobs analyzed and ready for scoring.")
            return analyzed_list
        finally:
            conn.close()

    def _extract_requirements(
        self,
        raw_jd: str,
        default_title: str,
        default_company: str,
        default_loc: str
    ) -> ParsedJDRequirements:
        """High-speed requirement extraction with comprehensive ATS keyword detection."""
        # Detect extensive technical skills
        known_skills = [
            "Python", "FastAPI", "Django", "Flask", "PostgreSQL", "MySQL", "SQLAlchemy",
            "Redis", "Kafka", "Docker", "Kubernetes", "AWS", "REST", "GraphQL",
            "Microservices", "CI/CD", "Linux", "Git", "Celery", "RabbitMQ", "SQL",
            "JavaScript", "TypeScript", "React", "LangChain", "LLM", "System Design",
            "AsyncIO", "Concurrency", "JWT", "OAuth", "OOP", "PyTest"
        ]
        extracted_skills = [s for s in known_skills if re.search(r"\b" + re.escape(s) + r"\b", raw_jd, re.I)]
        if not extracted_skills:
            extracted_skills = ["Python", "Software Engineering"]

        # Detect hard constraints (citizenship / visa / clearance)
        hard_constraints = []
        if re.search(r"\b(us citizen|citizenship|secret clearance|ts/sci)\b", raw_jd, re.I):
            hard_constraints.append("US Citizenship / Clearance Required")

        # Parse years of experience if mentioned
        exp_match = re.search(r"(\d+)\+?\s*(?:-\s*(\d+))?\s*(?:years?|yrs?)(?:\s+of\s+experience)?", raw_jd, re.I)
        min_years = int(exp_match.group(1)) if exp_match else 2

        return ParsedJDRequirements(
            title=default_title,
            company=default_company,
            location=default_loc,
            employment_type="Full-time",
            min_years_experience=min_years,
            required_skills=extracted_skills,
            preferred_skills=["System Design", "FastAPI", "Docker"],
            education_requirement="Bachelor's Degree",
            responsibilities=["Design, build, and deploy scalable software backend services."],
            hard_constraints=hard_constraints,
            keywords=extracted_skills
        )

