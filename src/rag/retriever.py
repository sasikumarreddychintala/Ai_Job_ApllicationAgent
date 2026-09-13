import re
import math
import numpy as np
from typing import List, Dict, Tuple, Optional
from src.resume.validator import CandidateProfile
from src.resume.profile import ProfileManager
from src.utils.logger import logger

# ---------------------------------------------------------------------------
# Lazy-loaded sentence-transformers model (cached once per process)
# Model: all-MiniLM-L6-v2 — ~80 MB, CPU-only, ~30ms per encode
# Graceful fallback to BM25 token-overlap if package not installed.
# ---------------------------------------------------------------------------
_ST_MODEL = None
_ST_AVAILABLE = None  # None = not yet checked; True/False after first check

def _get_st_model():
    """Returns cached SentenceTransformer model, or None if unavailable."""
    global _ST_MODEL, _ST_AVAILABLE
    if _ST_AVAILABLE is not None:
        return _ST_MODEL
    try:
        from sentence_transformers import SentenceTransformer
        _ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        _ST_AVAILABLE = True
        logger.info("🧠 [RAG] sentence-transformers loaded — cosine similarity active.")
    except Exception as e:
        _ST_AVAILABLE = False
        logger.info(f"ℹ️ [RAG] sentence-transformers not available ({e}). Using BM25 fallback.")
    return _ST_MODEL


class CandidateRAGStore:
    """
    Local, zero-paid-API semantic RAG store indexing candidate experience,
    achievements, and pre-approved answers.

    Retrieval strategy (priority):
      1. sentence-transformers cosine similarity (all-MiniLM-L6-v2) — semantic
      2. BM25-style token-overlap fallback (if package not installed)
    """

    def __init__(self, profile_manager: Optional[ProfileManager] = None):
        self.pm = profile_manager or ProfileManager()
        self._chunks: List[Dict[str, str]] = []
        self._embeddings: Optional[np.ndarray] = None  # shape (N, 384)
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

        # Pre-compute embeddings if model is available
        model = _get_st_model()
        if model and self._chunks:
            try:
                texts = [c["text"] for c in self._chunks]
                self._embeddings = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
                logger.info(f"🧠 [RAG] Indexed {len(self._chunks)} candidate chunks with semantic embeddings.")
            except Exception as e:
                logger.warning(f"⚠️ [RAG] Embedding pre-computation failed ({e}). BM25 fallback active.")
                self._embeddings = None
        else:
            self._embeddings = None

    def retrieve_relevant_context(self, query: str, top_k: int = 3) -> List[str]:
        """
        Returns top-k most relevant candidate knowledge chunks for the given query.

        Uses cosine similarity (sentence-transformers) when available for true semantic
        matching. Falls back to BM25-style token overlap if the library is not installed.
        """
        if not self._chunks:
            self._build_index()

        if not self._chunks:
            return []

        # --- Strategy 1: Cosine similarity via sentence-transformers ---
        model = _get_st_model()
        if model and self._embeddings is not None:
            try:
                q_emb = model.encode([query], convert_to_numpy=True, normalize_embeddings=True)  # (1, 384)
                # Cosine similarity = dot product when embeddings are L2-normalized
                scores = (self._embeddings @ q_emb.T).flatten()  # (N,)
                top_indices = np.argsort(scores)[::-1][:top_k]
                results = [self._chunks[i]["text"] for i in top_indices if scores[i] > 0.1]
                if results:
                    logger.info(
                        f"🧠 [RAG] Semantic retrieval: top score={scores[top_indices[0]]:.3f} | "
                        f"{len(results)} chunks for '{query[:40]}...'"
                    )
                    return results
            except Exception as e:
                logger.warning(f"⚠️ [RAG] Cosine similarity failed ({e}). Using BM25 fallback.")

        # --- Strategy 2: BM25-style token overlap fallback ---
        return self._bm25_retrieve(query, top_k)

    def _bm25_retrieve(self, query: str, top_k: int) -> List[str]:
        """BM25-style token overlap retrieval — used when sentence-transformers unavailable."""
        q_tokens = set(re.findall(r"\w+", query.lower()))
        if not q_tokens:
            return [c["text"] for c in self._chunks[:top_k]]

        scored: List[Tuple[float, str]] = []
        for chunk in self._chunks:
            text = chunk["text"]
            c_tokens = set(re.findall(r"\w+", text.lower()))
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

        logger.info(f"📝 [RAG] BM25 retrieved {len(results)} chunks for '{query[:40]}...'")
        return results

