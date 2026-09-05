import os
import json
import math
import urllib.request
import urllib.error
from typing import List, Optional
from config import settings
from src.utils.logger import logger

_EMBED_CACHE = {}

def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return max(0.0, min(1.0, dot_product / (norm_a * norm_b)))

def _fallback_token_similarity(text_a: str, text_b: str) -> float:
    import re
    words_a = set(re.findall(r'\b[a-zA-Z0-9_-]{2,}\b', text_a.lower()))
    words_b = set(re.findall(r'\b[a-zA-Z0-9_-]{2,}\b', text_b.lower()))
    if not words_a or not words_b:
        return 0.0
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return round(intersection / union, 3) if union > 0 else 0.0

class SemanticMatcher:
    @classmethod
    def get_embedding(cls, text: str) -> Optional[List[float]]:
        clean_text = text.strip()
        if not clean_text:
            return None
        text_hash = hash(clean_text[:500])
        if text_hash in _EMBED_CACHE:
            return _EMBED_CACHE[text_hash]

        api_key = (getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")).strip().strip("'\"")
        if not api_key:
            return None

        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
        payload = {
            "model": "models/text-embedding-004",
            "content": {"parts": [{"text": clean_text[:2000]}]}
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "JobAgent/2.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    values = data.get("embedding", {}).get("values", [])
                    if values:
                        _EMBED_CACHE[text_hash] = values
                        return values
        except Exception as e:
            logger.debug(f"Gemini embedding notice ({e}). Using token similarity fallback.")

        return None

    @classmethod
    def compute_semantic_similarity(cls, candidate_text: str, jd_text: str) -> float:
        if not candidate_text or not jd_text:
            return 0.0
        vec_cand = cls.get_embedding(candidate_text)
        if vec_cand:
            vec_jd = cls.get_embedding(jd_text)
            if vec_jd:
                cos_sim = _cosine_similarity(vec_cand, vec_jd)
                return round(cos_sim, 3)
        return _fallback_token_similarity(candidate_text, jd_text)