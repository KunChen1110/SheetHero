from typing import Optional
from dataclasses import dataclass

@dataclass
class Config:
    # === OpenAI Configuration ===
    api_key: str = ""
    base_url: Optional[str] = None
    deployment: str = "gpt-4o-mini"

    # === Processing Configuration ===
    max_turns: int = 3
    total_token_budget: int = 5000

    # === Output ===
    verbose: bool = False
    output_mode: str = "text" # "text" or "file"
    output_file: Optional[str] = None

    # === Timeouts and Retries ===
    max_retries: int = 3
    timeout: int = 30