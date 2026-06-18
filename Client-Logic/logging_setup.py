"""
logging_setup.py — Structured JSON logging configuration for ShadowDrive++ client.
"""

import os
import logging
import logging.handlers
import json
from datetime import datetime

import config

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)

def setup_logging():
    """Initializes logging with rotating file handlers and structured JSON formatter."""
    log_dir = os.path.join(config.BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "shadowdrive_client.log")

    # Root logger setup
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Clear existing handlers to prevent duplicate logging
    root_logger.handlers = []

    # Rotating File Handler (5 MB per file, max 5 backup files)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(JSONFormatter())
    file_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)

    # Console Handler for stdout
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    ))
    console_handler.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)

    logging.info("Logging initialized. Writing structured logs to: %s", log_file)
