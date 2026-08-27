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
        """Calls Groq Cloud API with automatic active model fallback."""
        clean_key = api_key.strip().strip("'\"")
        configured_model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile").strip().strip("'\"")
        # json_object mode is supported by llama-3 models on Groq — mixtral does NOT support it
        json_object_models = {"llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant", "llama3-70b-8192", "llama3-8b-8192"}
        candidate_models = [configured_model, "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "llama3-8b-8192"]
        # Deduplicate preserving order
        models_to_try = []
        for m in candidate_models:
            if m and m not in models_to_try:
                models_to_try.append(m)

        url = "https://api.groq.com/openai/v1/chat/completions"
        last_ex = None

        for model_name in models_to_try:
            try:
                use_json_mode = model_name in json_object_models
                payload = {
                    "model": model_name,
                    "messages": [
                        {"role": "system", "content": "You are an expert AI Job Application & Resume Tailoring Engine. Always respond in strict, valid JSON matching the requested schema exactly. Output only raw JSON with no markdown fences or extra text."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": temperature,
                }
                if use_json_mode:
                    payload["response_format"] = {"type": "json_object"}

                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Mozilla/5.0 (compatible; JobAgent/2.0)",
                        "Authorization": f"Bearer {clean_key}"
                    }
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8"))
                        content_str = data["choices"][0]["message"]["content"]
                        # Strip markdown fences if model ignored instructions
                        content_str = content_str.strip()
                        if content_str.startswith("```"):
                            content_str = content_str.split("```")[1]
                            if content_str.startswith("json"):
                                content_str = content_str[4:]
                        parsed = json.loads(content_str.strip())
                        validated = response_schema(**parsed)
                        logger.info(f" ⚡ [Groq {model_name}] Successfully generated {response_schema.__name__}!")
                        return validated
            except Exception as e:
                last_ex = e
                err_str = str(e)
                # 404 = model not found, 400 = bad request (often json_object unsupported) → try next model
                if "404" in err_str or "400" in err_str:
                    logger.debug(f"[Groq] Model {model_name} rejected ({err_str[:80]}), trying next...")
                    continue
                raise e

        raise last_ex or RuntimeError("Groq models exhausted")

    def _generate_gemini(
        self,
        prompt: str,
        response_schema: Type[T],
        api_key: str,
        temperature: float = 0.1
    ) -> T:
        """Calls Google Gemini Cloud API with automatic active model fallback."""
        clean_key = api_key.strip().strip("'\"")
        configured_model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash").strip().strip("'\"")
        # gemini-2.5-flash is free & most capable; fallback chain uses stable names
        candidate_models = [configured_model, "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash", "gemini-1.5-pro"]
        models_to_try = []
        for m in candidate_models:
            if m and m not in models_to_try:
                models_to_try.append(m)

        last_ex = None
        for model_name in models_to_try:
            for api_version in ("v1beta", "v1"):
                try:
                    url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model_name}:generateContent?key={clean_key}"
                    payload = {
                        "contents": [
                            {
                                "parts": [
                                    {"text": f"You are an expert AI Job Application & Resume Tailoring Engine. Always respond in strict, valid JSON matching the requested schema exactly. Output only raw JSON with no markdown fences.\n\n{prompt}"}
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
                            text_content = text_content.strip()
                            if text_content.startswith("```"):
                                text_content = text_content.split("```")[1]
                                if text_content.startswith("json"):
                                    text_content = text_content[4:]
                            parsed = json.loads(text_content.strip())
                            validated = response_schema(**parsed)
                            logger.info(f" 💎 [Gemini {model_name}] Successfully generated {response_schema.__name__}!")
                            return validated
                except Exception as e:
                    last_ex = e
                    if "404" in str(e):
                        logger.debug(f"[Gemini] {model_name} ({api_version}) not found, trying next...")
                        continue  # try next api_version or model
                    raise e

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
