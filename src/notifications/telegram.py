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

    def send_message(self, text: str) -> bool:
        """Dispatches formatted message to configured Telegram chat."""
        if not self.is_configured:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
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
        return False

    def send_document(self, file_path, caption: str = "") -> bool:
        """Uploads and delivers a PDF document directly to configured Telegram chat."""
        from pathlib import Path
        p = Path(file_path)
        if not self.is_configured or not p.exists():
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendDocument"

        try:
            import requests
            with open(p, "rb") as f:
                resp = requests.post(
                    url,
                    data={"chat_id": self.chat_id, "caption": caption},
                    files={"document": (p.name, f, "application/pdf")},
                    timeout=25
                )
            if resp.status_code == 200:
                logger.info(f" Delivered document '{p.name}' directly to Telegram.")
                return True
            else:
                logger.warning(f"Telegram document dispatch returned {resp.status_code}: {resp.text[:100]}")
        except Exception as e:
            logger.warning(f"Telegram document dispatch notice: {e}")

        return False

