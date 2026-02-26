"""app.logging_utils

Logging utilities:
- File logging for operational debugging / copying errors into Copilot
- Optional in-memory buffers can be added later; debug panels use TraceCollector
"""

from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def build_logger(log_dir: str, name: str = "company_text2sql") -> logging.Logger:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers in Streamlit reruns
    if logger.handlers:
        return logger

    log_path = Path(log_dir) / "app.log"
    handler = RotatingFileHandler(str(log_path), maxBytes=2_000_000, backupCount=5, encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    handler.setFormatter(fmt)
    logger.addHandler(handler)

    console = logging.StreamHandler()
    console.setFormatter(fmt)
    logger.addHandler(console)
    return logger
