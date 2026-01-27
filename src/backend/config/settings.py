from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict


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
    output_mode: str = "text"  # "text" or "file"
    output_file: Optional[str] = None

    # === Timeouts and Retries ===
    max_retries: int = 3
    timeout: int = 30

    def to_dict(self) -> Dict[str, Any]:
        """Convert this config instance to dictionary for UI rendering."""
        return asdict(self)

    def update(self, updates: Dict[str, Any]) -> None:
        """Update this config instance with values from a dictionary."""
        if not updates:
            return

        for key, value in updates.items():
            if hasattr(self, key):
                field_type = self.__annotations__.get(key)

                if value is not None:
                    try:
                        if field_type == int and isinstance(value, str):
                            setattr(self, key, int(value))
                        elif field_type == float and isinstance(value, str):
                            setattr(self, key, float(value))
                        elif field_type == bool and isinstance(value, str):
                            setattr(self, key, value.lower() in ('true', '1'))
                        else:
                            setattr(self, key, value)
                    except ValueError:
                        pass


class ConfigFactory:
    """Constructs Config instances and default settings."""

    @staticmethod
    def create(settings_dict: Optional[Dict[str, Any]] = None) -> Config:
        new_config = Config()

        if settings_dict:
            new_config.update(settings_dict)

        return new_config

    @staticmethod
    def get_default_settings_dict() -> Dict[str, Any]:
        return Config().to_dict()
