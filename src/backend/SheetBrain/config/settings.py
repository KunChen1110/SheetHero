# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""Configuration settings for SheetBrain."""

import os
from typing import Optional
from dataclasses import dataclass


@dataclass
class Config:
    """Configuration class for SheetBrain application."""

    # OpenAI Configuration
    api_key: str = "your_api_key"  # Will be overridden by OPENAI_API_KEY env var or raise error
    base_url: Optional[str] = None  # None means use OpenAI SDK default (https://api.openai.com/v1)
    deployment: str = "gpt-4o-mini"  # Default to gpt-4o-mini, can be overridden via OPENAI_DEPLOYMENT env var

    # Processing Configuration
    max_turns: int = 3
    total_token_budget: int = 5000

    # Features
    enable_validation: bool = True
    enable_understanding: bool = True

    # Timeouts and Retries
    max_retries: int = 3
    timeout: int = 30

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        # Get base_url from env, default to None (SDK will use default)
        base_url = os.getenv("OPENAI_BASE_URL")
        if not base_url or base_url == "your_base_url":
            base_url = None
        
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", cls.api_key),
            base_url=base_url,
            deployment=os.getenv("OPENAI_DEPLOYMENT", cls.deployment),
            max_turns=int(os.getenv("MAX_TURNS", cls.max_turns)),
            total_token_budget=int(os.getenv("TOKEN_BUDGET", cls.total_token_budget)),
            enable_validation=os.getenv("ENABLE_VALIDATION", "true").lower() == "true",
            enable_understanding=os.getenv("ENABLE_UNDERSTANDING", "true").lower() == "true",
            max_retries=int(os.getenv("MAX_RETRIES", cls.max_retries)),
            timeout=int(os.getenv("TIMEOUT", cls.timeout))
        )