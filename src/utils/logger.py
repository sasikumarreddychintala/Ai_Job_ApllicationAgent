import logging
import sys
from pathlib import Path
from rich.logging import RichHandler
from config import settings

def setup_logger(name: str = "agent") -> logging.Logger:
    """Configures a rich console and file logger."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    # Avoid duplicate handlers if already initialized
    if logger.handlers:
        return logger

    # Console Handler (Rich)
    rich_handler = RichHandler(rich_tracebacks=True, markup=True)
    rich_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))
    console_formatter = logging.Formatter("%(message)s")
    rich_handler.setFormatter(console_formatter)
    logger.addHandler(rich_handler)

    # File Handler
    log_file = settings.LOGS_DIR / "agent.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s"
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    return logger

logger = setup_logger()
