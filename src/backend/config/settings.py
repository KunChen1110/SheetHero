from typing import Optional
from dataclasses import dataclass

@dataclass
class Config:
    # === OpenAI Configuration ===
    api_key: str = "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"
    base_url: Optional[str] = None
    deployment: str = "gpt-4o-mini"

    # === Processing Configuration ===
    max_turns: int = 3
    total_token_budget: int = 5000

    # === Output ===
    output_mode: str = "text" # "text" or "file"
    output_file: Optional[str] = None

    # === Timeouts and Retries ===
    max_retries: int = 3
    timeout: int = 30