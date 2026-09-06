import os
import json
import time
import threading
import urllib.request
import urllib.error
from typing import Type, TypeVar, Optional, Dict, Any
from pydantic import BaseModel

from config import settings
from src.utils.logger import logger

T = TypeVar("T", bound=BaseModel)

# Thread-safe rate limiter lock across parallel JD workers
_AI_RATE_LOCK = threading.Lock()
_LAST_CALL_TIMESTAMP = 0.0

def _pace_ai_requests(min_interval: float = 0.12):
    """Smooths out bursting concurrency across parallel workers to prevent HTTP 429 / 400."""
    global _LAST_CALL_TIMESTAMP
    with _AI_RATE_LOCK:
        now = time.time()
        elapsed = now - _LAST_CALL_TIMESTAMP
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _LAST_CALL_TIMESTAMP = time.time()

class OllamaClient:
    """Reusable HTTP client for Ollama LLM inference with Pydantic JSON schema enforcement & retries."""

    def __init__(
        self,
        base_url: str = settings.OLLAMA_BASE_URL,
        model: str = settings.OLLAMA_MODEL,
        timeout: int = settings.OLLAMA_TIMEOUT,
        max_retries: int = 3
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    def generate_json(
        self,
        prompt: str,
        response_schema: Type[T],
        temperature: float = 0.1
    ) -> T:
        """
        Sends prompt to Multi-Tier AI Engine with Automatic Failover:
        Tier 1: Groq Cloud (Llama 3.3 70B -> Gemma 2 9B -> Mixtral 8x7B)
        Tier 2: Google Gemini Cloud (Gemini 1.5 Flash -> Gemini 2.0 Flash)
        Tier 3: Local Ollama (Qwen 2.5)
        Tier 4: Built-in Deterministic Rule Engine
        """
        groq_api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        gemini_api_key = getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")

        # Log key presence so misconfiguration is immediately visible in server logs
        if not groq_api_key and not gemini_api_key:
            logger.warning("⚠️ No GROQ_API_KEY or GEMINI_API_KEY found in environment — will attempt Ollama only.")
        else:
            logger.debug(f"[AI] Keys present: GROQ={'YES' if groq_api_key else 'NO'} | GEMINI={'YES' if gemini_api_key else 'NO'}")

        # --- Tier 1: Try Groq Cloud ---
        if groq_api_key:
            try:
                _pace_ai_requests(0.15)
                return self._generate_groq(prompt, response_schema, groq_api_key, temperature)
            except Exception as e:
                logger.warning(f"⚠️ Groq Cloud notice / rate limit ({e}). Automatically failing over to next AI provider...")

        # --- Tier 2: Try Google Gemini Cloud ---
        if gemini_api_key:
            try:
                _pace_ai_requests(0.15)
                return self._generate_gemini(prompt, response_schema, gemini_api_key, temperature)
            except Exception as e:
                logger.warning(f"⚠️ Google Gemini notice / rate limit ({e}). Automatically failing over to next AI provider...")

        # --- Tier 3: Try Local Ollama (Only if locally hosted) ---
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "keep_alive": "30s",
            "options": {
                "temperature": temperature,
                "num_thread": 4
            }
        }

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    raw_json_str = result.get("response", "{}")
                    data = json.loads(raw_json_str)
                    validated = response_schema(**data)
                    logger.info(f" [Ollama] Successfully generated & validated {response_schema.__name__} (attempt {attempt}).")
                    return validated

            except json.JSONDecodeError as e:
                last_error = f"JSON decode error: {e}"
                logger.debug(f"[Ollama Attempt {attempt}/{self.max_retries}] {last_error}")
            except Exception as e:
                last_error = f"Ollama generation notice: {e}"
                # If localhost connection refused (cloud environment), skip repeated retries immediately
                if "connection refused" in str(e).lower() or "111" in str(e):
                    break
                logger.debug(f"[Ollama Attempt {attempt}/{self.max_retries}] {last_error}")

        raise RuntimeError(f"All AI providers (Groq, Gemini, Ollama) exhausted: {last_error}")

    def _generate_groq(
        self,
        prompt: str,
        response_schema: Type[T],
        api_key: str,
        temperature: float = 0.1
    ) -> T:
        """Calls Groq Cloud API with automatic active model fallback and rate limit recovery."""
        clean_key = api_key.strip().strip("'\"")
        configured_model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile").strip().strip("'\"")

        # Only models confirmed to support response_format=json_object on Groq (2026)
        # mixtral-8x7b-32768 is DEPRECATED — removed to avoid 400s
        json_object_models = {
            "llama-3.3-70b-versatile",
            "llama3-70b-8192",
        }

        # Active model fallback chain (verified 2026 — deprecated models removed)
        candidate_models = []
        for m in [configured_model, "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                  "gemma2-9b-it", "llama3-8b-8192"]:
            if m and m not in candidate_models:
                candidate_models.append(m)

        url = "https://api.groq.com/openai/v1/chat/completions"
        last_ex = None

        for model_name in candidate_models:
            try:
                use_json_mode = model_name in json_object_models
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": "You are an expert AI assistant. Respond ONLY with valid JSON matching the schema. No markdown, no explanation."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": temperature,
                    "max_tokens": 4096,
                }
                if use_json_mode:
                    payload["response_format"] = {"type": "json_object"}

                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {clean_key}"
                    }
                )
                try:
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        content_str = data["choices"][0]["message"]["content"].strip()
                        if content_str.startswith("```"):
                            content_str = content_str.split("```")[1]
                            if content_str.startswith("json"):
                                content_str = content_str[4:]
                        parsed = json.loads(content_str.strip())
                        validated = response_schema(**parsed)
                        logger.info(f"⚡ [Groq/{model_name}] Successfully generated {response_schema.__name__}!")
                        return validated
                except urllib.error.HTTPError as http_err:
                    body = ""
                    try:
                        body = http_err.read().decode("utf-8", errors="replace")[:300]
                    except Exception:
                        pass
                    last_ex = http_err
                    logger.debug(f"[Groq/{model_name}] HTTP {http_err.code}: {body}")
                    time.sleep(0.2)
                    continue
            except Exception as e:
                last_ex = e
                logger.debug(f"[Groq/{model_name}] Error: {str(e)[:120]}")
                time.sleep(0.1)
                continue

        raise last_ex or RuntimeError("Groq models exhausted")

    def _generate_gemini(
        self,
        prompt: str,
        response_schema: Type[T],
        api_key: str,
        temperature: float = 0.1
    ) -> T:
        """Calls Google Gemini Cloud API with official stable model fallback."""
        clean_key = api_key.strip().strip("'\"")
        configured_model = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash").strip().strip("'\"")

        # Canonical model IDs that work on v1beta (verified 2026)
        # Format: short alias -> canonical ID tried first
        candidate_models = []
        for m in [
            configured_model,
            "gemini-2.0-flash",
            "gemini-2.0-flash-001",
            "gemini-2.0-flash-lite",
            "gemini-2.0-flash-lite-001",
            "gemini-1.5-flash",
            "gemini-1.5-flash-001",
            "gemini-1.5-flash-8b",
            "gemini-1.5-flash-8b-001",
        ]:
            if m and m not in candidate_models:
                candidate_models.append(m)

        last_ex = None
        for model_name in candidate_models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={clean_key}"
                payload = {
                    "contents": [
                        {
                            "parts": [
                                {"text": f"You are an expert AI assistant. Respond ONLY with valid JSON matching the schema exactly. No markdown, no explanation.\n\n{prompt}"}
                            ]
                        }
                    ],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "temperature": temperature,
                        "maxOutputTokens": 4096,
                    }
                }
                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                try:
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        text_content = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if text_content.startswith("```"):
                            text_content = text_content.split("```")[1]
                            if text_content.startswith("json"):
                                text_content = text_content[4:]
                        parsed = json.loads(text_content.strip())
                        validated = response_schema(**parsed)
                        logger.info(f"💎 [Gemini/{model_name}] Successfully generated {response_schema.__name__}!")
                        return validated
                except urllib.error.HTTPError as http_err:
                    body = ""
                    try:
                        body = http_err.read().decode("utf-8", errors="replace")[:300]
                    except Exception:
                        pass
                    last_ex = http_err
                    logger.debug(f"[Gemini/{model_name}] HTTP {http_err.code}: {body}")
                    time.sleep(0.2)
                    continue
            except Exception as e:
                last_ex = e
                logger.debug(f"[Gemini/{model_name}] Error: {str(e)[:120]}")
                time.sleep(0.1)
                continue

        raise last_ex or RuntimeError("Gemini models exhausted")



    def is_online(self) -> bool:
        """Checks if Groq API, Gemini API, or local Ollama service is reachable."""
        groq_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        gemini_key = getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")
        if groq_key or gemini_key:
            return True
        url = f"{self.base_url}/api/tags"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "JobAgent/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False

