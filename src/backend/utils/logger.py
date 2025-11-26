# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Logging utilities for SheetBrain."""

import logging
import sys
from typing import Optional, List

_REGISTERED_LOGGERS: List[logging.Logger] = []


def _register_logger(logger: logging.Logger) -> None:
    """Keep track of loggers so we can adjust their levels later."""
    if logger not in _REGISTERED_LOGGERS:
        _REGISTERED_LOGGERS.append(logger)


def setup_logger(
    name: str = "sheetbrain",
    level: int = logging.INFO,
    format_string: Optional[str] = None
) -> logging.Logger:
    """
    Set up a logger with consistent formatting.

    Args:
        name: Logger name
        level: Logging level
        format_string: Custom format string

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        _register_logger(logger)
        return logger

    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    formatter = logging.Formatter(format_string)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.setLevel(level)
    _register_logger(logger)

    return logger


def set_log_level(level: int) -> None:
    """Update the logging level for all registered SheetBrain loggers."""
    for logger in _REGISTERED_LOGGERS:
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)