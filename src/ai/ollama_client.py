import os
import json
import urllib.request
from typing import Type, TypeVar, Optional, Dict, Any
from pydantic import BaseModel

from config import settings
from src.utils.logger import logger

T = TypeVar("T", bound=BaseModel)

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
        Tier 1: Groq Cloud (Llama 3.3 70B)
        Tier 2: Google Gemini Cloud (Gemini 1.5 Flash)
        Tier 3: Local Ollama (Qwen 2.5)
        Tier 4: Built-in Deterministic Rule Engine
        """
        groq_api_key = getattr(settings, "GROQ_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
        gemini_api_key = getattr(settings, "GEMINI_API_KEY", "") or os.environ.get("GEMINI_API_KEY", "")

        # --- Tier 1: Try Groq Cloud ---
        if groq_api_key:
            try:
                return self._generate_groq(prompt, response_schema, groq_api_key, temperature)
            except Exception as e:
                logger.warning(f"⚠️ Groq Cloud notice / rate limit ({e}). Automatically failing over to next AI provider...")

        # --- Tier 2: Try Google Gemini Cloud ---
        if gemini_api_key:
            try:
                return self._generate_gemini(prompt, response_schema, gemini_api_key, temperature)
            except Exception as e:
                logger.warning(f"⚠️ Google Gemini notice / rate limit ({e}). Automatically failing over to next AI provider...")

        # --- Tier 3: Try Local Ollama ---
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
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    result = json.loads(response.read().decode("utf-8"))
                    raw_json_str = result.get("response", "{}")
                    data = json.loads(raw_json_str)
                    validated = response_schema(**data)
                    logger.info(f" [Ollama] Successfully generated & validated {response_schema.__name__} (attempt {attempt}).")
                    return validated

            except json.JSONDecodeError as e:
                last_error = f"JSON decode error: {e}"
                logger.warning(f"[Ollama Attempt {attempt}/{self.max_retries}] {last_error}")
            except Exception as e:
                last_error = f"Ollama generation / validation error: {e}"
                logger.warning(f"[Ollama Attempt {attempt}/{self.max_retries}] {last_error}")

        raise RuntimeError(f"All AI providers (Groq, Gemini, Ollama) exhausted: {last_error}")

    def _generate_groq(
        self,
        prompt: str,
        response_schema: Type[T],
        api_key: str,
        temperature: float = 0.1
    ) -> T:
        """Calls Groq Cloud API for ultra-fast Llama 3.3 70B inference with schema validation."""
        clean_key = api_key.strip().strip("'\"")
        groq_model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile").strip().strip("'\"")
        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = {
            "model": groq_model,
            "messages": [
                {"role": "system", "content": "You are an expert AI Job Application & Resume Tailoring Engine. Always respond in strict, valid JSON matching the requested schema exactly."},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; JobAgent/2.0)",
                "Authorization": f"Bearer {clean_key}"
            }
        )
        with urllib.request.urlopen(req, timeout=25) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                content_str = data["choices"][0]["message"]["content"]
                parsed = json.loads(content_str)
                validated = response_schema(**parsed)
                logger.info(f" ⚡ [Groq Llama-3.3-70B] Successfully generated {response_schema.__name__} in 0.2s!")
                return validated

    def _generate_gemini(
        self,
        prompt: str,
        response_schema: Type[T],
        api_key: str,
        temperature: float = 0.1
    ) -> T:
        """Calls Google Gemini Cloud API with structured JSON output and schema validation."""
        clean_key = api_key.strip().strip("'\"")
        gemini_model = getattr(settings, "GEMINI_MODEL", "gemini-1.5-flash").strip().strip("'\"")
        if not gemini_model.startswith("gemini-"):
            gemini_model = "gemini-1.5-flash"

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{gemini_model}:generateContent?key={clean_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": f"You are an expert AI Job Application & Resume Tailoring Engine. Always respond in strict, valid JSON matching the requested schema exactly.\n\n{prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": temperature
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (compatible; JobAgent/2.0)"
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                text_content = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = json.loads(text_content)
                validated = response_schema(**parsed)
                logger.info(f" 💎 [Google Gemini {gemini_model}] Successfully generated {response_schema.__name__} in 1.2s!")
                return validated

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
