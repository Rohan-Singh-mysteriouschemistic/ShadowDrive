"""
logging_setup.py — Loguru logging configuration for ShadowDrive++ client.
"""

import os
import sys

import config
from loguru import logger


def setup_logging():
    """Configure loguru for ShadowDrive client."""
    logger.remove()

    # Console output (colored, human-readable)
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # File output (rotated)
    log_dir = os.path.join(config.BASE_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)
    logger.add(
        os.path.join(log_dir, "shadowdrive_client.log"),
        rotation="5 MB",
        retention=5,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    logger.info("Loguru logging initialized.")
