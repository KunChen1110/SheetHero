"""Logging utilities for SheetHero."""

import logging
import sys
from typing import Optional, List


# Central registry of all SheetHero loggers for global level control
_REGISTERED_LOGGERS: List[logging.Logger] = []


def _register_logger(logger: logging.Logger) -> None:
    """
    Track logger in registry for global level adjustments.

    This enables set_log_level() to update all SheetHero loggers simultaneously,
    providing centralized control over logging verbosity across the application.
    """

    if logger not in _REGISTERED_LOGGERS:
        _REGISTERED_LOGGERS.append(logger)


def setup_logger(
    name: str = "sheethero",
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    to_console: bool = False
) -> logging.Logger:
    #Set up a logger with consistent formatting.
    logger = logging.getLogger(name)

    # Return existing logger if already configured
    if logger.handlers:
        _register_logger(logger)
        return logger

    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logger.setLevel(level)
    
    # Only add StreamHandler if explicitly requested
    # Default behavior is file-only logging to avoid CLI clutter
    if to_console:
        formatter = logging.Formatter(format_string)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    _register_logger(logger)

    return logger


def set_log_level(level: int) -> None:
    """ Update the logging level for all registered SheetHero loggers."""

    for logger in _REGISTERED_LOGGERS:
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)