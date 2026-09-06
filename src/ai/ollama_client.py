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

_CACHED_GEMINI_MODELS: list = []
_CACHED_GROQ_MODELS: list = []

def _get_live_gemini_models(clean_key: str) -> list:
    global _CACHED_GEMINI_MODELS
    if _CACHED_GEMINI_MODELS:
        return _CACHED_GEMINI_MODELS
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={clean_key}"
        req = urllib.request.Request(
            url,
            headers={"x-goog-api-key": clean_key, "User-Agent": "JobApplicationAgent/2.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            live = []
            for m in data.get("models", []):
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    name = m.get("name", "").replace("models/", "")
                    if "flash" in name and name not in live:
                        live.append(name)
            for m in data.get("models", []):
                methods = m.get("supportedGenerationMethods", [])
                if "generateContent" in methods:
                    name = m.get("name", "").replace("models/", "")
                    if name not in live:
                        live.append(name)
            if live:
                _CACHED_GEMINI_MODELS = live
                logger.info(f"🟢 [Gemini] Auto-discovered {len(live)} active models: {live[:4]}")
                return live
    except Exception as e:
        logger.warning(f"⚠️ [Gemini] Model auto-discovery notice: {e}")
    return ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]

def _get_live_groq_models(clean_key: str) -> list:
    global _CACHED_GROQ_MODELS
    if _CACHED_GROQ_MODELS:
        return _CACHED_GROQ_MODELS
    try:
        url = "https://api.groq.com/openai/v1/models"
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {clean_key}", "User-Agent": "JobApplicationAgent/2.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            live = []
            for m in data.get("data", []):
                m_id = m.get("id", "")
                if m_id and not any(skip in m_id.lower() for skip in ["whisper", "guard", "embed", "moderation"]):
                    live.append(m_id)
            if live:
                _CACHED_GROQ_MODELS = live
                logger.info(f"🟢 [Groq] Auto-discovered {len(live)} active models: {live[:4]}")
                return live
    except Exception as e:
        logger.warning(f"⚠️ [Groq] Model auto-discovery notice: {e}")
    return ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

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

    def _unwrap_schema_dict(self, parsed: Any, schema_cls: Type[T]) -> Dict[str, Any]:
        """Unwraps any top-level key an LLM may wrap the JSON in (e.g. {'profile': {...}})."""
        if not isinstance(parsed, dict):
            return parsed
        schema_fields = set(getattr(schema_cls, "model_fields", {}).keys())
        if schema_fields and not (schema_fields & set(parsed.keys())):
            for val in parsed.values():
                if isinstance(val, dict) and (schema_fields & set(val.keys())):
                    return val
        return parsed


    def _generate_groq(
        self,
        prompt: str,
        response_schema: Type[T],
        api_key: str,
        temperature: float = 0.1
    ) -> T:
        """Calls Groq Cloud API with dynamic model discovery and active model fallback."""
        clean_key = api_key.strip().strip("'\"")
        configured_model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile").strip().strip("'\"")

        # Dynamically discover what models are live for this key
        live_models = _get_live_groq_models(clean_key)
        candidate_models = []
        if configured_model in live_models:
            candidate_models.append(configured_model)
        for m in live_models:
            if m not in candidate_models:
                candidate_models.append(m)

        url = "https://api.groq.com/openai/v1/chat/completions"
        last_ex = None

        for model_name in candidate_models[:6]:
            for try_json_format in (True, False):
                try:
                    payload = {
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": "You are an expert AI assistant. Respond ONLY with a valid JSON object matching the requested schema. Output raw JSON only with no markdown fences."},
                            {"role": "user", "content": f"{prompt}\n\nPlease output valid JSON only."}
                        ],
                        "temperature": temperature,
                        "max_tokens": 4096,
                    }
                    if try_json_format:
                        payload["response_format"] = {"type": "json_object"}

                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {clean_key}",
                            "User-Agent": "JobApplicationAgent/2.0"
                        }
                    )
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        content_str = data["choices"][0]["message"]["content"].strip()
                        if content_str.startswith("```"):
                            content_str = content_str.split("```")[1]
                            if content_str.startswith("json"):
                                content_str = content_str[4:]
                        parsed = json.loads(content_str.strip())
                        unwrapped = self._unwrap_schema_dict(parsed, response_schema)
                        validated = response_schema(**unwrapped)
                        logger.info(f"⚡ [Groq/{model_name}] Successfully generated {response_schema.__name__}!")
                        return validated

                except urllib.error.HTTPError as http_err:
                    body = ""
                    try:
                        body = http_err.read().decode("utf-8", errors="replace")[:300]
                    except Exception:
                        pass
                    last_ex = http_err
                    if try_json_format and http_err.code == 400:
                        continue
                    logger.warning(f"⚠️ [Groq/{model_name}] HTTP {http_err.code}: {body}")
                    time.sleep(0.2)
                    break
                except Exception as e:
                    last_ex = e
                    logger.warning(f"⚠️ [Groq/{model_name}] Error: {str(e)[:120]}")
                    time.sleep(0.1)
                    break

        raise last_ex or RuntimeError("Groq models exhausted")

    def _generate_gemini(
        self,
        prompt: str,
        response_schema: Type[T],
        api_key: str,
        temperature: float = 0.1
    ) -> T:
        """Calls Google Gemini Cloud API with dynamic model discovery and active model fallback."""
        clean_key = api_key.strip().strip("'\"")
        configured_model = getattr(settings, "GEMINI_MODEL", "gemini-2.5-flash").strip().strip("'\"")

        # Dynamically discover what models are live for this key
        live_models = _get_live_gemini_models(clean_key)
        candidate_models = []
        if configured_model in live_models:
            candidate_models.append(configured_model)
        for m in live_models:
            if m not in candidate_models:
                candidate_models.append(m)

        last_ex = None
        for model_name in candidate_models[:6]:
            for use_mime_type in (True, False):
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={clean_key}"
                    gen_config = {
                        "temperature": temperature,
                        "maxOutputTokens": 4096,
                    }
                    if use_mime_type:
                        gen_config["responseMimeType"] = "application/json"

                    payload = {
                        "contents": [
                            {
                                "parts": [
                                    {"text": f"You are an expert AI assistant. Respond ONLY with valid JSON matching the schema exactly. No markdown, no explanation.\n\n{prompt}\n\nPlease output valid JSON only."}
                                ]
                            }
                        ],
                        "generationConfig": gen_config
                    }
                    req = urllib.request.Request(
                        url,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": clean_key,
                            "User-Agent": "JobApplicationAgent/2.0"
                        }
                    )
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        text_content = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        if text_content.startswith("```"):
                            text_content = text_content.split("```")[1]
                            if text_content.startswith("json"):
                                text_content = text_content[4:]
                        parsed = json.loads(text_content.strip())
                        unwrapped = self._unwrap_schema_dict(parsed, response_schema)
                        validated = response_schema(**unwrapped)
                        logger.info(f"💎 [Gemini/{model_name}] Successfully generated {response_schema.__name__}!")
                        return validated

                except urllib.error.HTTPError as http_err:
                    body = ""
                    try:
                        body = http_err.read().decode("utf-8", errors="replace")[:300]
                    except Exception:
                        pass
                    last_ex = http_err
                    if use_mime_type and http_err.code in (400, 404):
                        continue
                    logger.warning(f"⚠️ [Gemini/{model_name}] HTTP {http_err.code}: {body}")
                    time.sleep(0.2)
                    break
                except Exception as e:
                    last_ex = e
                    logger.warning(f"⚠️ [Gemini/{model_name}] Error: {str(e)[:120]}")
                    time.sleep(0.1)
                    break

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

