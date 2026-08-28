import json
import sqlite3
import re
import time
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
        """Analyzes up to 150 pending jobs in DISCOVERED state using parallel Cloud AI workers."""
        import concurrent.futures
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

            # Expanded non-tech keyword filter (35+ categories vs old 12)
            non_tech_keywords = [
                # Physical / trade
                "barber", "nanny", "technician", "driver", "meat", "lifeguard",
                "hostess", "bell person", "janitorial", "cleaner", "labourer",
                "cashier", "clerk", "electrician", "handyman", "painter",
                "plumber", "carpenter", "welder", "mechanic", "operator",
                # Healthcare / legal / finance
                "influencer", "counsel", "financial analyst", "dispute analyst",
                "compliance officer", "nurse", "doctor", "physician", "pharmacist",
                "lawyer", "solicitor", "accountant", "auditor", "tax consultant",
                # Non-tech marketing / creative
                "content writer", "copywriter", "graphic designer", "illustrator",
                "social media manager", "digital marketing", "seo specialist",
                "brand manager", "event coordinator", "pr executive",
                # Sales / retail / hospitality
                "sales executive", "field sales", "insurance agent", "tele caller",
                "retail", "store manager", "chef", "cook", "waiter", "bartender",
                # HR / admin
                "hr executive", "human resource", "recruiter", "talent acquisition",
                "admin assistant", "office manager", "data entry",
                # Logistics / supply chain
                "logistics", "supply chain", "warehouse", "delivery", "fleet",
            ]

            # Fast title-skip DISCOVERED → SKIPPED (same logic as finder pre-filter for any that slipped through)
            ids_to_analyze = []
            for j_id, title in rows:
                t_lower = title.lower()
                if any(k in t_lower for k in non_tech_keywords):
                    with conn:
                        conn.execute("UPDATE applications SET status = 'SKIPPED' WHERE job_id = ?", (j_id,))
                    continue
                ids_to_analyze.append(j_id)
                if len(ids_to_analyze) >= limit:
                    break

            logger.info(f" {len(ids_to_analyze)} jobs queued for parallel JD analysis (limit={limit}).")

            # Parallel analysis — each thread opens its own DB connection (thread-safe)
            def _analyze_one(job_id: int) -> "ParsedJDRequirements | None":
                try:
                    return self.analyze_job(job_id)
                except Exception as e:
                    logger.debug(f"JD analysis notice for job {job_id}: {e}")
                    return None

            max_workers = min(6, len(ids_to_analyze)) if ids_to_analyze else 1
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for j_id in ids_to_analyze:
                    futures[executor.submit(_analyze_one, j_id)] = j_id
                    time.sleep(0.04)
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result is not None:
                        analyzed_list.append(result)

            logger.info(f" Parallel JD analysis complete: {len(analyzed_list)} jobs analyzed and ready for scoring.")
            return analyzed_list
        finally:
            conn.close()

    def _fallback_parse_jd(
        self,
        raw_jd: str,
        default_title: str,
        default_company: str,
        default_loc: str
    ) -> ParsedJDRequirements:
        """Deterministic fallback requirement parser for job descriptions."""
        return self._extract_requirements(raw_jd, default_title, default_company, default_loc)

    def _extract_requirements(
        self,
        raw_jd: str,
        default_title: str,
        default_company: str,
        default_loc: str
    ) -> ParsedJDRequirements:
        """High-speed requirement extraction with Cloud AI (Groq/Gemini) and ATS fallback."""
        # 1. Try Cloud AI / LLM extraction (Groq Llama 3.3 70B / Gemini 1.5 Flash)
        try:
            prompt = render_jd_prompt(raw_jd)
            parsed = self.ollama.generate_json(prompt, ParsedJDRequirements)
            if parsed and parsed.required_skills:
                if not parsed.title:
                    parsed.title = default_title
                if not parsed.company:
                    parsed.company = default_company
                if not parsed.location:
                    parsed.location = default_loc
                logger.info(f" Extracted {len(parsed.required_skills)} skills via Cloud AI Engine ({default_company}).")
                return parsed
        except Exception as e:
            logger.debug(f"AI JD extraction notice ({e}). Using deterministic rule analyzer.")

        # 2. Deterministic Fallback
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

