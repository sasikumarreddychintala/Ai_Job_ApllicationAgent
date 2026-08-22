import json
import urllib.request
from typing import Optional, Dict, Any, List
from config import settings
from src.utils.logger import logger

class DiscordNotifier:
    """Dispatches free, rich mobile & desktop alerts via standard Discord Webhooks."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or getattr(settings, "DISCORD_WEBHOOK_URL", "")

    @property
    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("http"))

    def send_embed(self, title: str, description: str, color: int = 0x38bdf8, fields: Optional[List[Dict[str, Any]]] = None) -> bool:
        """Dispatches a formatted rich Discord Embed."""
        if not self.is_configured:
            return False

        embed = {
            "title": title,
            "description": description,
            "color": color,
            "footer": {"text": "Personal AI Job Application Agent"}
        }
        if fields:
            embed["fields"] = fields

        payload = {"embeds": [embed]}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.webhook_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 204):
                    logger.info("[NOTIFIER] Discord webhook notification dispatched successfully.")
                    return True
        except Exception as e:
            logger.warning(f"[NOTIFIER] Discord notification dispatch notice: {e}")

        return False

    def send_message(self, text: str) -> bool:
        """Sends a simple plain text message to Discord."""
        return self.send_embed(title="Job Agent Notification", description=text)

