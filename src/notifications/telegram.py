import json
import urllib.request
from typing import Optional
from config import settings
from src.utils.logger import logger

class TelegramNotifier:
    """Sends free mobile push alerts via the standard Telegram Bot API."""

    def __init__(
        self,
        bot_token: Optional[str] = getattr(settings, "TELEGRAM_BOT_TOKEN", None),
        chat_id: Optional[str] = getattr(settings, "TELEGRAM_CHAT_ID", None)
    ):
        self.bot_token = bot_token
        self.chat_id = chat_id

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def send_message(self, text: str, reply_markup: Optional[dict] = None) -> bool:
        """Dispatches formatted message to configured Telegram chat with optional inline buttons."""
        if not self.is_configured:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    logger.info(" Telegram notification dispatched successfully.")
                    return True
        except Exception as e:
            logger.warning(f"Telegram notification dispatch notice: {e}")
            # Robust fallback: Try sending without parse_mode in case markdown entities caused an error
            try:
                fallback_payload = dict(payload)
                fallback_payload.pop("parse_mode", None)
                fallback_data = json.dumps(fallback_payload).encode("utf-8")
                fallback_req = urllib.request.Request(
                    url,
                    data=fallback_data,
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(fallback_req, timeout=10) as f_resp:
                    if f_resp.status == 200:
                        logger.info(" Telegram notification dispatched via plain-text fallback.")
                        return True
            except Exception as fe:
                logger.warning(f"Telegram notification fallback notice: {fe}")
        return False

    def send_document(self, file_path, caption: str = "") -> bool:
        """Uploads and delivers a PDF document directly to configured Telegram chat."""
        from pathlib import Path
        p = Path(file_path)
        if not self.is_configured or not p.exists():
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"

        for attempt in range(2):
            try:
                import requests
                with open(p, "rb") as f:
                    resp = requests.post(
                        url,
                        data={"chat_id": self.chat_id, "caption": caption},
                        files={"document": (p.name, f, "application/pdf")},
                        timeout=60
                    )
                if resp.status_code == 200:
                    logger.info(f" Delivered document '{p.name}' directly to Telegram.")
                    return True
                else:
                    logger.warning(f"Telegram document dispatch returned {resp.status_code}: {resp.text[:100]}")
            except Exception as e:
                if attempt == 1:
                    logger.warning(f"Telegram document dispatch notice: {e}")
                import time
                time.sleep(1.5)

        return False

