"""Logging utilities for SheetHero."""

import logging
import sys
from typing import Optional, List


class LoggerRegistry:
    """Central registry of SheetHero loggers for global level control."""

    _registered_loggers: List[logging.Logger] = []

    @classmethod
    def _register_logger(cls, logger: logging.Logger) -> None:
        if logger not in cls._registered_loggers:
            cls._registered_loggers.append(logger)

    @classmethod
    def setup_logger(
        cls,
        name: str = "sheethero",
        level: int = logging.INFO,
        format_string: Optional[str] = None,
        to_console: bool = False
    ) -> logging.Logger:
        logger = logging.getLogger(name)

        if logger.handlers:
            cls._register_logger(logger)
            return logger

        if format_string is None:
            format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

        logger.setLevel(level)

        if to_console:
            formatter = logging.Formatter(format_string)
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        cls._register_logger(logger)
        return logger

    @classmethod
    def set_log_level(cls, level: int) -> None:
        for logger in cls._registered_loggers:
            logger.setLevel(level)
            for handler in logger.handlers:
                handler.setLevel(level)
