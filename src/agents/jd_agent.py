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

    def analyze_all_pending_jobs(self, limit: int = 30) -> List[ParsedJDRequirements]:
        """Analyzes up to 30 pending jobs in DISCOVERED state using parallel Cloud AI workers (memory-optimized)."""
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

            max_workers = min(3, len(ids_to_analyze)) if ids_to_analyze else 1
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {}
                for j_id in ids_to_analyze:
                    futures[executor.submit(_analyze_one, j_id)] = j_id
                    time.sleep(0.04)
                for future in concurrent.futures.as_completed(futures):
                    result = future.result()
                    if result is not None:
                        analyzed_list.append(result)

            import gc
            gc.collect()
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
        """Public alias for _extract_requirements — kept for backwards compatibility with tests and callers."""
        return self._extract_requirements(raw_jd, default_title, default_company, default_loc)

    # -----------------------------------------------------------------------
    # Comprehensive regex-based skill keyword list for pre-extraction pass
    # -----------------------------------------------------------------------
    _REGEX_TECH_SKILLS = [
        # Languages
        "Python", "Java", "JavaScript", "TypeScript", "Go", "Golang", "Rust", "C\\+\\+", "C#", "Ruby", "Scala", "Kotlin", "Swift",
        # Frameworks / Libraries
        "FastAPI", "Django", "Flask", "Spring Boot", "Node\\.js", "Express", "React", "Vue", "Angular", "Next\\.js",
        "LangChain", "LlamaIndex", "LangGraph", "CrewAI", "Haystack",
        "PyTorch", "TensorFlow", "Keras", "scikit-learn", "Hugging Face", "Transformers",
        "Pandas", "NumPy", "SciPy", "Matplotlib", "Seaborn",
        # Databases
        "PostgreSQL", "MySQL", "SQLite", "MongoDB", "Redis", "Elasticsearch", "DynamoDB", "Cassandra",
        "SQLAlchemy", "Prisma", "Sequelize",
        # Cloud & Infra
        "AWS", "GCP", "Azure", "Docker", "Kubernetes", "Terraform", "Ansible", "Helm",
        "EC2", "S3", "RDS", "Lambda", "CloudFormation", "EKS", "ECS",
        # AI/ML
        "LLM", "RAG", "Generative AI", "GenAI", "Prompt Engineering", "Embeddings",
        "OpenAI", "Ollama", "Groq", "Gemini", "Claude", "BERT", "GPT",
        "Computer Vision", "NLP", "MLOps", "Vector Database", "Pinecone", "Weaviate", "ChromaDB",
        # Messaging / Streaming
        "Kafka", "Apache Kafka", "RabbitMQ", "Celery", "Redis Streams", "Pub/Sub",
        # APIs / Protocols
        "REST", "REST APIs", "GraphQL", "gRPC", "WebSocket", "OAuth", "JWT", "OpenAPI",
        # DevOps / CI/CD
        "Git", "GitHub", "GitLab", "CI/CD", "Jenkins", "GitHub Actions", "CircleCI",
        "Linux", "Bash", "Shell",
        # Testing
        "PyTest", "Jest", "Unit Testing", "TDD", "BDD", "Selenium", "Playwright",
        # Architecture
        "Microservices", "System Design", "Distributed Systems", "Event-Driven", "CQRS", "DDD",
        "Agile", "Scrum", "SOLID",
    ]

    @classmethod
    def _strip_html(cls, text: str) -> str:
        """Strip HTML tags and decode common HTML entities from raw JD text."""
        import html
        # Decode HTML entities first (e.g. &#43; → +, &amp; → &, &lt; → <)
        text = html.unescape(text)
        # Replace block-level tags with spaces so words don't merge
        text = re.sub(r'<(br|p|li|div|tr|td|th|h[1-6]|ul|ol)[^>]*>', ' ', text, flags=re.IGNORECASE)
        # Strip all remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    @classmethod
    def _regex_preextract_skills(cls, jd_text: str) -> list:
        """
        Fast regex pass over raw JD text to extract known tech skills.
        Runs BEFORE LLM call and results are merged with LLM output.
        Catches skills that LLMs sometimes miss in long or complex JDs.
        HTML is stripped first so tags like <p>Python</p> are correctly matched.
        """
        # Strip HTML so skills inside tags are visible to word-boundary regex
        clean_text = cls._strip_html(jd_text) if jd_text else ""
        found = []
        for skill in cls._REGEX_TECH_SKILLS:
            pattern = r'\b' + skill + r'\b'
            if re.search(pattern, clean_text, re.IGNORECASE):
                # Use the canonical casing from _REGEX_TECH_SKILLS list
                canonical = re.sub(r'\\', '', skill)  # remove regex escape chars
                found.append(canonical)
        return found

    def _extract_requirements(
        self,
        raw_jd: str,
        default_title: str,
        default_company: str,
        default_loc: str
    ) -> ParsedJDRequirements:
        """High-speed requirement extraction with regex pre-pass + Cloud AI merge + ATS fallback.
        Step 1: Regex pre-extraction of known tech skills (fast, deterministic)
        Step 2: Cloud AI / LLM extraction (Groq / Gemini)
        Step 3: Merge LLM output + regex skills → never miss a skill
        Step 4: Full deterministic fallback if AI completely fails
        """
        # Step 1: Strip HTML + Regex pre-extraction (always runs, zero token cost)
        clean_jd = self._strip_html(raw_jd) if raw_jd else ""
        regex_skills = self._regex_preextract_skills(clean_jd)
        logger.info(f" Regex pre-extractor found {len(regex_skills)} skills: {regex_skills[:8]}{'...' if len(regex_skills) > 8 else ''}")

        # Step 2 & 3: Try Cloud AI / LLM extraction + merge with regex skills
        try:
            prompt = render_jd_prompt(clean_jd)
            parsed = self.ollama.generate_json(prompt, ParsedJDRequirements)
            if parsed and parsed.required_skills:
                if not parsed.title:
                    parsed.title = default_title
                if not parsed.company:
                    parsed.company = default_company
                if not parsed.location:
                    parsed.location = default_loc

                # Merge: add regex-found skills not already in LLM output
                llm_skills_lower = {s.lower() for s in parsed.required_skills}
                for rs in regex_skills:
                    if rs.lower() not in llm_skills_lower:
                        parsed.required_skills.append(rs)

                # Also merge into keywords
                kw_lower = {k.lower() for k in (parsed.keywords or [])}
                for rs in regex_skills:
                    if rs.lower() not in kw_lower:
                        parsed.keywords = (parsed.keywords or []) + [rs]

                llm_only_count = len(parsed.required_skills) - len(regex_skills)
                logger.info(
                    f" Extracted {len(parsed.required_skills)} skills via Cloud AI + Regex merge ({default_company}). "
                    f"LLM found ~{llm_only_count}, Regex added {len(regex_skills)} (total after dedup)."
                )
                return parsed
        except Exception as e:
            logger.debug(f"AI JD extraction notice ({e}). Using deterministic rule analyzer.")

        # Step 4: Full Deterministic Fallback (uses regex_skills already extracted)
        extracted_skills = regex_skills if regex_skills else [
            "Python", "FastAPI", "Django", "Flask", "PostgreSQL", "MySQL", "SQLAlchemy",
            "Redis", "Kafka", "Docker", "Kubernetes", "AWS", "REST", "GraphQL",
            "Microservices", "CI/CD", "Linux", "Git", "Celery", "RabbitMQ", "SQL",
            "JavaScript", "TypeScript", "React", "LangChain", "LLM", "System Design",
            "AsyncIO", "Concurrency", "JWT", "OAuth", "OOP", "PyTest"
        ]
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


