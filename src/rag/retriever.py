import re
import math
from typing import List, Dict, Tuple, Optional
from src.resume.validator import CandidateProfile
from src.resume.profile import ProfileManager
from src.utils.logger import logger

class CandidateRAGStore:
    """Local, zero-paid-API RAG store indexing candidate experience, achievements, and pre-approved answers."""

    def __init__(self, profile_manager: Optional[ProfileManager] = None):
        self.pm = profile_manager or ProfileManager()
        self._chunks: List[Dict[str, str]] = []
        self._build_index()

    def _build_index(self) -> None:
        profile = self.pm.load_profile()
        if not profile:
            return

        self._chunks = []

        # 1. Index Work Experience Chunks
        for exp in profile.experience:
            chunk_text = (
                f"Work Experience at {exp.company} as {exp.position} ({exp.start_date} to {exp.end_date}):\n"
                f"• Highlights: {' | '.join(exp.highlights)}\n"
                f"• Verified Technologies: {', '.join(exp.verified_skills)}"
            )
            self._chunks.append({
                "type": "experience",
                "title": f"{exp.position} at {exp.company}",
                "text": chunk_text
            })

        # 2. Index Education Chunks
        for edu in profile.education:
            chunk_text = f"Education: {edu.degree} in {edu.field_of_study or 'CS'} from {edu.institution} ({edu.graduation_year or 'Completed'})"
            self._chunks.append({
                "type": "education",
                "title": edu.degree,
                "text": chunk_text
            })

        # 3. Index Skills Chunk
        if profile.skills:
            self._chunks.append({
                "type": "skills",
                "title": "Technical Skills",
                "text": f"Candidate Core Technical Skills & Tooling: {', '.join(profile.skills)}"
            })

        # 4. Index Custom Answers
        for k, v in profile.custom_answers.items():
            self._chunks.append({
                "type": "custom_answer",
                "title": k,
                "text": f"Pre-Approved Answer for {k}: {v}"
            })

    def retrieve_relevant_context(self, query: str, top_k: int = 3) -> List[str]:
        """Scores candidate knowledge chunks using BM25 / token matching and returns top relevant text snippets."""
        if not self._chunks:
            self._build_index()

        q_tokens = set(re.findall(r"\w+", query.lower()))
        if not q_tokens:
            return [c["text"] for c in self._chunks[:top_k]]

        scored: List[Tuple[float, str]] = []
        for chunk in self._chunks:
            text = chunk["text"]
            c_tokens = set(re.findall(r"\w+", text.lower()))

            # Intersection and term frequency score
            overlap = q_tokens.intersection(c_tokens)
            if not overlap:
                score = 0.0
            else:
                score = sum(1.0 for token in overlap) / (math.log(len(c_tokens) + 1) + 1.0)

            scored.append((score, text))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [text for score, text in scored if score > 0][:top_k]
        
        # If no positive matches, fallback to first top_k
        if not results and self._chunks:
            results = [c["text"] for c in self._chunks[:top_k]]

        logger.info(f" RAG retrieved {len(results)} relevant candidate context snippets for query: '{query[:40]}...'")
        return results
