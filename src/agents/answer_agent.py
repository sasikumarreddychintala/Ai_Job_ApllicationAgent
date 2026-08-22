import json
import sqlite3
import hashlib
from typing import List, Optional, Tuple

from config import settings
from src.utils.logger import logger
from src.database.models import init_db
from src.resume.profile import ProfileManager
from src.ai.schemas import ApplicationAnswerOutput
from src.ai.ollama_client import OllamaClient
from src.ai.prompts.answer_prompt import render_answer_prompt
from src.automation.question_classifier import classify_question, QuestionCategory

def hash_question(question_text: str) -> str:
    """Generates SHA-256 hash string for question lookup in database."""
    clean = question_text.lower().strip()
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()

class ApplicationAnswerAgent:
    """Agent responsible for classifying questions, looking up approved answers, and generating truthful application answers."""

    def __init__(
        self,
        profile_manager: Optional[ProfileManager] = None,
        ollama_client: Optional[OllamaClient] = None,
        db_path=settings.DATABASE_PATH
    ):
        self.profile_manager = profile_manager or ProfileManager()
        self.ollama = ollama_client or OllamaClient()
        self.db_path = db_path

    def answer_question(self, question_text: str, job_id: Optional[int] = None, conn: Optional[sqlite3.Connection] = None) -> ApplicationAnswerOutput:
        """Answers an application question truthfully based on candidate profile facts or approved answers."""
        should_close = False
        if conn is None:
            conn = init_db(self.db_path)
            should_close = True

        try:
            profile = self.profile_manager.load_profile()
            if not profile:
                raise ValueError("Candidate profile not found. Please import master resume first.")

            cat = classify_question(question_text)
            c = profile.contact_info

            # 1. Direct Contact Info Mapping
            if cat == QuestionCategory.FULL_NAME:
                return self._create_output(question_text, c.full_name, is_known=True)
            elif cat == QuestionCategory.EMAIL:
                return self._create_output(question_text, c.email, is_known=True)
            elif cat == QuestionCategory.PHONE and c.phone:
                return self._create_output(question_text, c.phone, is_known=True)
            elif cat == QuestionCategory.LOCATION and c.location:
                return self._create_output(question_text, c.location, is_known=True)
            elif cat == QuestionCategory.LINKEDIN and c.linkedin:
                return self._create_output(question_text, c.linkedin, is_known=True)
            elif cat == QuestionCategory.GITHUB and c.github:
                return self._create_output(question_text, c.github, is_known=True)
            elif cat == QuestionCategory.PORTFOLIO and c.portfolio:
                return self._create_output(question_text, c.portfolio, is_known=True)

            # 2. Check Candidate Profile Pre-Approved Custom Answers
            if cat.value in profile.custom_answers:
                val = profile.custom_answers[cat.value]
                return self._create_output(question_text, val, is_known=True)

            # 3. Check SQLite DB for Previously User-Approved Answers
            db_answer = self._lookup_db_answer(question_text, conn)
            if db_answer:
                return self._create_output(question_text, db_answer, is_known=True)

            # 4. Open-Ended Generation via Ollama + RAG Context
            if self.ollama.is_online():
                try:
                    from src.rag.retriever import CandidateRAGStore
                    rag = CandidateRAGStore(profile_manager=self.profile_manager)
                    rag_snippets = rag.retrieve_relevant_context(question_text, top_k=2)
                    rag_context_str = "\n---\n".join(rag_snippets)

                    prof_data = profile.model_dump()
                    prof_data["relevant_project_evidence"] = rag_snippets
                    prof_json = json.dumps(prof_data, ensure_ascii=False)

                    prompt = render_answer_prompt(question_text, prof_json)
                    out = self.ollama.generate_json(prompt, ApplicationAnswerOutput)
                    self._save_answer_to_db(question_text, out.answer, source="GENERATED", conn=conn)
                    return out
                except Exception as e:
                    logger.warning(f"Ollama question answering failed ({e}). Falling back to manual review flag.")

            # 5. Fallback for Unknown / Ambiguous Questions -> Pause for Manual Action
            logger.info(f" Question requires manual user review: '{question_text}'")
            return self._create_output(
                question_text,
                answer="[MANUAL_ACTION_REQUIRED]",
                is_known=False,
                requires_manual_review=True
            )

        finally:
            if should_close:
                conn.close()

    def process_answers_for_job(self, job_id: int, questions: List[str]) -> List[ApplicationAnswerOutput]:
        """Processes a list of application questions for a specific job."""
        conn = init_db(self.db_path)
        results = []
        try:
            for q in questions:
                out = self.answer_question(q, job_id=job_id, conn=conn)
                results.append(out)

            # If any answer requires manual review, flag application in DB
            has_unknown = any(out.requires_manual_review for out in results)
            if has_unknown:
                with conn:
                    conn.execute(
                        "UPDATE applications SET status = 'MANUAL_ACTION_REQUIRED', updated_at = CURRENT_TIMESTAMP WHERE job_id = ?",
                        (job_id,)
                    )
                logger.warning(f" Job ID {job_id} requires manual answer review. Status set to MANUAL_ACTION_REQUIRED.")

            return results
        finally:
            conn.close()

    def record_user_approved_answer(self, question_text: str, approved_answer: str) -> None:
        """Saves user-approved answer into database for future reuse across applications."""
        conn = init_db(self.db_path)
        try:
            self._save_answer_to_db(question_text, approved_answer, source="USER_APPROVED", conn=conn)
            logger.info(f" Saved user-approved answer for: '{question_text}'")
        finally:
            conn.close()

    def _create_output(
        self,
        question: str,
        answer: str,
        is_known: bool = True,
        requires_manual_review: bool = False
    ) -> ApplicationAnswerOutput:
        return ApplicationAnswerOutput(
            question=question,
            answer=answer,
            is_known=is_known,
            requires_manual_review=requires_manual_review
        )

    def _lookup_db_answer(self, question_text: str, conn: sqlite3.Connection) -> Optional[str]:
        q_hash = hash_question(question_text)
        cursor = conn.cursor()
        cursor.execute("SELECT answer_text FROM application_answers WHERE question_hash = ?", (q_hash,))
        row = cursor.fetchone()
        return row[0] if row else None

    def _save_answer_to_db(self, question_text: str, answer_text: str, source: str, conn: sqlite3.Connection) -> None:
        q_hash = hash_question(question_text)
        with conn:
            conn.execute(
                """
                INSERT INTO application_answers (question_hash, question_text, answer_text, source)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(question_hash) DO UPDATE SET answer_text = excluded.answer_text, source = excluded.source
                """,
                (q_hash, question_text, answer_text, source)
            )
