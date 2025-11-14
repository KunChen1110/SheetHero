# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

"""
 * Centralized configuration management for the SheetBrain application.
 *
 * This file defines the Config class, which acts as a single source of truth for
 * all settings: API credentials, model selection, analysis behavior, and timeouts.
 *
 * Two ways to configure:
 * 1. Environment variables (recommended for security and flexibility)
 * 2. Direct instantiation (useful for programmatic control)
 *
 * Environment Variable Naming Convention:
 * - OPENAI_* for API-related settings
 * - MAX_TURNS, TOKEN_BUDGET for processing limits
 * - ENABLE_* for feature toggles (use "true"/"false" strings)
 *
 * @author: Microsoft Corporation
 * @license: MIT License
"""

# Import the 'os' module to read operating system environment variables
# These are key-value pairs set outside your code (e.g., export OPENAI_API_KEY="...")
import os

# Import type hint for optional values that may be None
from typing import Optional

# Import dataclass decorator: automatically generates __init__, __repr__, etc.
# This saves us from writing boilerplate code for a simple data container
from dataclasses import dataclass


@dataclass
class Config:
    """
     * Configuration dataclass for SheetBrain.
     *
     * This class holds all settings needed to run the Excel analysis agent.
     * Using @dataclass means Python automatically creates:
     * - An __init__ method (constructor)
     * - A __repr__ method (for debugging output)
     * - Comparison methods (equals, not equals)
     *
     * All fields have default values, so you can create a Config with zero arguments
     * and then override only what you need.
     *
     * @field api_key: OpenAI API authentication key (required)
     * @field base_url: Custom API endpoint URL (optional, for Azure/non-OpenAI)
     * @field deployment: AI model name to use for analysis
     * @field max_turns: How many times AI can refine its answer
     * @field total_token_budget: Maximum tokens AI can use (affects cost/speed)
     * @field enable_validation: Whether AI double-checks its work
     * @field enable_understanding: Whether AI pre-analyzes Excel structure
     * @field max_retries: How many times to retry failed API calls
     * @field timeout: Seconds to wait before giving up on API calls
    """

    # === OpenAI Configuration ===
    # These settings control how we connect to the AI service

    api_key: str = "your_api_key"
    """
     * OpenAI API authentication key.
     * 
     * Default: "your_api_key" (placeholder - will cause error if not changed)
     * Environment Variable Override: OPENAI_API_KEY
     * 
     * This is a secret key that proves who you are. Get it from OpenAI's website.
     * WARNING: Never commit your real API key to version control!
    """

    base_url: Optional[str] = None
    """
     * Custom API endpoint URL.
     * 
     * Default: None (uses OpenAI's standard URL: https://api.openai.com/v1)
     * Environment Variable Override: OPENAI_BASE_URL
     * 
     * Set this only if using:
     * - Azure OpenAI Service (your custom Azure endpoint)
     * - Local AI models (e.g., Ollama, LocalAI)
     * - OpenAI-compatible API proxies
     * 
     * When None, the OpenAI SDK automatically uses the official endpoint.
    """

    deployment: str = "gpt-4o-mini"
    """
     * AI model name/deployment ID.
     * 
     * Default: "gpt-4o-mini" (fast, cheap, good for most Excel analysis)
     * Environment Variable Override: OPENAI_DEPLOYMENT
     * 
     * Common alternatives:
     * - "gpt-4o" (more capable but slower/more expensive)
     * - "gpt-3.5-turbo" (older, cheaper)
     * - For Azure: use your deployment name (e.g., "my-gpt4-deployment")
     * 
     * The model must support function calling and reasoning about tabular data.
    """

    # === Processing Configuration ===
    # These control how the AI analyzes the Excel file

    max_turns: int = 3
    """
     * Maximum number of analysis iterations.
     * 
     * Default: 3
     * Environment Variable Override: MAX_TURNS
     * 
     * Think of this as "how many times the AI can think again and improve":
     * - 1: One-shot answer (fastest, less accurate for complex questions)
     * - 3: Default (balanced - can revise answer twice if needed)
     * - 5+: More thorough (slower but better for complex analysis)
     * 
     * Each turn costs tokens and time, so balance accuracy vs. budget.
    """

    total_token_budget: int = 5000
    """
     * Maximum tokens for AI context generation.
     * 
     * Default: 5000
     * Environment Variable Override: TOKEN_BUDGET
     * 
     * "Tokens" are pieces of text (roughly 0.75 words each). This budget limits:
     * - How much Excel data we can send to the AI
     * - Length of AI's reasoning steps
     * - Total cost (you pay per token)
     * 
     * Increase if analyzing large files or getting "context too long" errors.
     * Decrease to save money on smaller files.
    """

    # === Feature Toggles ===
    # These enable/disable stages of the analysis pipeline

    enable_validation: bool = True
    """
     * Enable AI self-validation of answers.
     * 
     * Default: True
     * Environment Variable Override: ENABLE_VALIDATION
     * 
     * When True, after generating an answer, the AI asks itself:
     * "Is this answer correct? Does it match the data? Let me verify."
     * 
     * This catches errors but uses ~30% more tokens and time.
     * Set to False for faster, cheaper analysis when speed is critical.
    """

    enable_understanding: bool = True
    """
     * Enable Excel structure pre-analysis.
     * 
     * Default: True
     * Environment Variable Override: ENABLE_UNDERSTANDING
     * 
     * When True, before answering, the AI first studies:
     * - Column names, data types, and formats
     * - Table structure, headers, merged cells
     * - Potential data quality issues
     * 
     * This improves accuracy for complex files but uses extra tokens.
     * Set to False for very simple files to save time.
    """

    # === Timeouts and Retries ===
    # These improve reliability when network/API issues occur

    max_retries: int = 3
    """
     * Maximum retry attempts for failed API calls.
     * 
     * Default: 3
     * Environment Variable Override: MAX_RETRIES
     * 
     * If the AI service is slow/down, we'll retry this many times before giving up.
     * Each retry waits a bit longer (exponential backoff).
    """

    timeout: int = 30
    """
     * API call timeout in seconds.
     * 
     * Default: 30
     * Environment Variable Override: TIMEOUT
     * 
     * How long to wait for the AI to respond before giving up.
     * Increase if you have slow network or analyzing huge files.
     * Decrease for faster failure detection.
    """

    @classmethod
    def from_env(cls) -> "Config":
        """
         * Factory method: Create Config from environment variables.
         *
         * This method reads settings from your system's environment variables
         * and returns a fully configured Config object. It's the recommended
         * way to create configurations because:
         *
         * 1. **Security**: API keys stay out of your source code
         * 2. **Flexibility**: Same code works in different environments
         * 3. **12-Factor App**: Follows modern cloud deployment best practices
         *
         * How Environment Variables Are Read:
         * - os.getenv("VAR_NAME", default_value) reads the variable or uses default
         * - Boolean vars expect "true" or "false" (case-insensitive)
         * - Integer vars are converted from strings to numbers
         *
         * Environment Variables Supported:
         * - OPENAI_API_KEY: Your API key (required)
         * - OPENAI_BASE_URL: Custom endpoint (optional)
         * - OPENAI_DEPLOYMENT: Model name (default: gpt-4o-mini)
         * - MAX_TURNS: Analysis iterations (default: 3)
         * - TOKEN_BUDGET: Token limit (default: 5000)
         * - ENABLE_VALIDATION: "true" or "false" (default: true)
         * - ENABLE_UNDERSTANDING: "true" or "false" (default: true)
         * - MAX_RETRIES: Retry attempts (default: 3)
         * - TIMEOUT: Seconds to wait (default: 30)
         *
         * @param cls: The Config class itself (automatic, you don't pass this)
         * @return: A new Config instance populated from environment variables
         * @throws: ValueError if the environment variable cannot be converted to int
        """

        # Get base_url from environment, but treat "your_base_url" as "not set"
        # This handles cases where someone copies a template without editing
        base_url = os.getenv("OPENAI_BASE_URL")
        if not base_url or base_url == "your_base_url":
            base_url = None  # Explicitly set to None to use SDK default

        # Create and return a new Config instance with values from environment
        # Each os.getenv() call: read env var or fall back to class default
        # int() converts string values to integers (env vars are always strings)
        # .lower() == "true" converts string "true"/"false" to boolean True/False
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