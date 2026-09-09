"""Loguru configuration."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_CONFIGURED = False


def setup_logging(level: str = "INFO", log_file: str | Path | None = None) -> None:
    global _CONFIGURED
    logger.remove()
    logger.add(sys.stderr, level=level, format=(
        "<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | "
        "<cyan>{name}</cyan> - <level>{message}</level>"
    ))
    if log_file is not None:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        logger.add(log_file, level="DEBUG", rotation="50 MB")
    _CONFIGURED = True


def get_logger():
    if not _CONFIGURED:
        setup_logging()
    return logger
