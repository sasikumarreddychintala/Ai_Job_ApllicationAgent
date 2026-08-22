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
        Sends prompt to Ollama, parses JSON output, and validates against response_schema.
        Retries up to max_retries on malformed JSON or validation errors.
        """
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
                    
                    # Parse JSON
                    data = json.loads(raw_json_str)
                    
                    # Validate Pydantic Schema
                    validated = response_schema(**data)
                    logger.info(f" Successfully generated and validated {response_schema.__name__} (attempt {attempt}).")
                    return validated

            except json.JSONDecodeError as e:
                last_error = f"JSON decode error: {e}"
                logger.warning(f"[Attempt {attempt}/{self.max_retries}] {last_error}")
            except Exception as e:
                last_error = f"Ollama generation / validation error: {e}"
                logger.warning(f"[Attempt {attempt}/{self.max_retries}] {last_error}")

        raise RuntimeError(f"Ollama JSON generation failed after {self.max_retries} attempts: {last_error}")

    def is_online(self) -> bool:
        """Checks if local Ollama service is reachable."""
        url = f"{self.base_url}/api/tags"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "JobAgent/1.0"})
            with urllib.request.urlopen(req, timeout=3) as resp:
                return resp.status == 200
        except Exception:
            return False
